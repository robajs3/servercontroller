"""Docker + stosy compose. Rejestrowane przez agent.py, jeśli jest pakiet `docker`."""
import glob, os, re, shutil, subprocess, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
import docker
from flask import Blueprint, Response, abort, jsonify, request

bp = Blueprint("dockerapi", __name__)
_client = None
ID_RE = re.compile(r"^[0-9a-f]{12,64}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")

def cli():
    global _client
    if _client is None:
        _client = docker.from_env(timeout=20)
    return _client

def summarize(a):
    st, cfg = a["State"], a["Config"]
    labels = cfg.get("Labels") or {}
    ports = (a.get("NetworkSettings") or {}).get("Ports") or {}
    pub = sorted({f"{b['HostPort']}→{p.split('/')[0]}" for p, bs in ports.items() if bs for b in bs})
    return {"id": a["Id"][:12], "name": a["Name"].lstrip("/"), "image": cfg.get("Image"),
            "state": st.get("Status"), "running": bool(st.get("Running")),
            "health": (st.get("Health") or {}).get("Status"),
            "started_at": st.get("StartedAt"), "finished_at": st.get("FinishedAt"),
            "exit_code": st.get("ExitCode"), "oom": bool(st.get("OOMKilled")),
            "restarts": a.get("RestartCount", 0),
            "project": labels.get("com.docker.compose.project"),
            "service": labels.get("com.docker.compose.service"), "ports": pub}

def calc_stats(s):
    cpu, pre = s["cpu_stats"], s["precpu_stats"]
    d_cpu = cpu["cpu_usage"]["total_usage"] - pre["cpu_usage"]["total_usage"]
    d_sys = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
    n = cpu.get("online_cpus") or len(cpu["cpu_usage"].get("percpu_usage") or [1])
    pct = d_cpu / d_sys * n * 100 if d_sys > 0 and d_cpu > 0 else 0.0
    m = s["memory_stats"]; st = m.get("stats", {})
    used = m.get("usage", 0) - st.get("inactive_file", st.get("cache", 0))
    return round(pct, 1), max(used, 0), m.get("limit", 0)

def _inspect(i):
    try:
        return cli().api.inspect_container(i)
    except Exception:
        return None

def _stats(c):
    try:
        return calc_stats(cli().api.stats(c["id"], stream=False))
    except Exception:
        return None

@bp.get("/docker/containers")
def containers():
    try:
        ids = [c["Id"] for c in cli().api.containers(all=True)]
        with ThreadPoolExecutor(8) as ex:
            out = [summarize(a) for a in ex.map(_inspect, ids) if a]
        if request.args.get("stats") == "1":
            running = [c for c in out if c["running"]]
            with ThreadPoolExecutor(8) as ex:
                for c, r in zip(running, ex.map(_stats, running)):
                    if r:
                        c["cpu"], c["mem"], c["mem_limit"] = r
    except Exception as e:
        return jsonify(error=f"{type(e).__name__}: {e}"[:300]), 503
    return jsonify(containers=sorted(out, key=lambda c: c["name"]), ts=time.time())

@bp.post("/docker/containers/<cid>/<act>")
def c_action(cid, act):
    if not ID_RE.match(cid) or act not in ("start", "stop", "restart"):
        abort(400)
    try:
        getattr(cli().containers.get(cid), act)()
    except docker.errors.NotFound:
        abort(404)
    except Exception as e:
        return jsonify(error=f"{type(e).__name__}: {e}"[:300]), 502
    return jsonify(ok=True)

@bp.get("/docker/containers/<cid>/logs")
def c_logs(cid):
    if not ID_RE.match(cid):
        abort(400)
    try:
        tail = max(1, min(int(request.args.get("tail", 200)), 1000))
        raw = cli().api.logs(cid, tail=tail, timestamps=True, stdout=True, stderr=True)
    except Exception as e:
        return jsonify(error=f"{type(e).__name__}: {e}"[:300]), 502
    return Response(raw.decode("utf-8", "replace")[-200_000:], mimetype="text/plain")

# ---------------- stosy compose ----------------
STACK_ROOT = os.getenv("AGENT_STACKS_ROOT", "/opt/stacks")
EXTRA_DIRS = [p.strip() for p in os.getenv("AGENT_STACK_DIRS", "").split(",") if p.strip()]
COMPOSE_NAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
ACTIONS = {"up": ["up", "-d"], "down": ["down"], "pull": ["pull"], "restart": ["restart"]}

def compose_file(d):
    return next((n for n in COMPOSE_NAMES if os.path.isfile(os.path.join(d, n))), None)

def registry():
    dirs = []
    if os.path.isdir(STACK_ROOT):
        dirs += [os.path.join(STACK_ROOT, x) for x in sorted(os.listdir(STACK_ROOT))]
    dirs += EXTRA_DIRS
    out = {}
    for d in dirs:
        d = os.path.realpath(d)
        f = compose_file(d) if os.path.isdir(d) else None
        if not f:
            continue
        name = re.sub(r"[^A-Za-z0-9_.-]", "-", os.path.basename(d))[:50] or "stack"
        while name in out:
            name += "-2"
        out[name] = {"name": name, "path": d, "file": f}
    return out

def _stack(name):
    return registry().get(name) or abort(404)

def _fname(s, kind):
    if kind == "compose":
        return s["file"]
    if kind == "env":
        return ".env"
    abort(404)

def validate(s, content):
    cand = os.path.join(s["path"], ".panel-candidate.yml")
    try:
        with open(cand, "w") as f:
            f.write(content)
        r = subprocess.run(["docker", "compose", "-f", cand, "config", "-q"], cwd=s["path"],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stderr or r.stdout).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        try:
            os.remove(cand)
        except OSError:
            pass

def write_file(path, content):
    bak = None
    if os.path.exists(path):
        bak = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, bak)
        for old in sorted(glob.glob(path + ".bak-*"))[:-5]:
            os.remove(old)
        with open(path, "w") as f:           # w miejscu: zachowuje właściciela i uprawnienia
            f.write(content)
    else:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if path.endswith(".env") else 0o644)
        with os.fdopen(fd, "w") as f:
            f.write(content)
    return bak

@bp.get("/stacks")
def stacks():
    return jsonify(stacks=list(registry().values()), root=STACK_ROOT)

@bp.get("/stacks/<name>/files/<kind>")
def file_get(name, kind):
    s = _stack(name); fn = _fname(s, kind)
    p = os.path.join(s["path"], fn)
    if not os.path.isfile(p):
        return jsonify(content="", exists=False, file=fn)
    with open(p, errors="replace") as f:
        return jsonify(content=f.read(300_000), exists=True, file=fn)

@bp.put("/stacks/<name>/files/<kind>")
def file_put(name, kind):
    s = _stack(name); fn = _fname(s, kind)
    content = (request.get_json(silent=True) or {}).get("content")
    if not isinstance(content, str) or len(content) > 200_000:
        abort(400)
    if content and not content.endswith("\n"):
        content += "\n"
    warn = ""
    if kind == "compose":
        ok, out = validate(s, content)
        if not ok:
            return jsonify(ok=False, error=out), 422
        warn = out
    try:
        bak = write_file(os.path.join(s["path"], fn), content)
    except OSError as e:
        return jsonify(ok=False, error=f"Zapis nieudany: {e}"), 500
    return jsonify(ok=True, backup=bak, warnings=warn)

@bp.post("/stacks")
def stack_new():
    d = request.get_json(silent=True) or {}
    name, content = d.get("name", ""), d.get("content", "")
    if not NAME_RE.match(name) or not isinstance(content, str) or not content.strip() or len(content) > 200_000:
        abort(400)
    path = os.path.join(STACK_ROOT, name)
    if os.path.exists(path):
        return jsonify(ok=False, error="Stos o tej nazwie już istnieje"), 409
    try:
        os.makedirs(path)
        s = {"path": path, "file": "docker-compose.yml"}
        ok, out = validate(s, content if content.endswith("\n") else content + "\n")
        if not ok:
            shutil.rmtree(path, ignore_errors=True)
            return jsonify(ok=False, error=out), 422
        write_file(os.path.join(path, s["file"]), content if content.endswith("\n") else content + "\n")
    except OSError as e:
        shutil.rmtree(path, ignore_errors=True)
        return jsonify(ok=False, error=f"{e}"), 500
    return jsonify(ok=True, name=name)

# ---------------- zadania (up/pull/... trwają długo) ----------------
JOBS, RUNNING, LOCK = {}, set(), threading.Lock()

def _run_job(j, s):
    try:
        p = subprocess.Popen(["docker", "compose", *ACTIONS[j["action"]]], cwd=s["path"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        timer = threading.Timer(900, p.kill); timer.start()
        for line in p.stdout:
            if len(j["output"]) < 100_000:
                j["output"] += line
        j["rc"] = p.wait(); timer.cancel()
    except Exception as e:
        j["output"] += f"\n{type(e).__name__}: {e}"; j["rc"] = -1
    finally:
        j["status"] = "done"
        with LOCK:
            RUNNING.discard(s["name"])

@bp.post("/stacks/<name>/<action>")
def stack_action(name, action):
    s = _stack(name)
    if action not in ACTIONS:
        abort(404)
    with LOCK:
        if name in RUNNING:
            return jsonify(error="operacja już trwa"), 409
        RUNNING.add(name)
        j = {"id": uuid.uuid4().hex[:12], "stack": name, "action": action,
             "status": "running", "output": "", "rc": None, "started": time.time()}
        JOBS[j["id"]] = j
        for old in sorted(JOBS.values(), key=lambda x: x["started"])[:-30]:
            JOBS.pop(old["id"], None)
    threading.Thread(target=_run_job, args=(j, s), daemon=True).start()
    return jsonify(job=j["id"])

@bp.get("/jobs/<jid>")
def job(jid):
    return jsonify(JOBS.get(jid) or abort(404))
