import os, re
from datetime import timedelta
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, abort, jsonify, make_response, render_template, request
from flask_login import current_user, login_required
from markupsafe import escape
from sqlalchemy import text
from . import agents, dockerstate as ds
from .extensions import db, limiter
from .models import ContainerEvent, DockerState, now
from .routes import RANGES, audit, ph

dbp = Blueprint("dock", __name__)
# kontenery tych projektów compose można tylko uruchamiać (nie zatrzymasz panelu z panelu)
PROTECTED = {x.strip() for x in os.getenv("PROTECTED_PROJECTS", "servercontroller").split(",") if x.strip()}
ID = re.compile(r"^[0-9a-f]{12}$")
NAME = re.compile(r"^[A-Za-z0-9_.-]{1,60}$")

@dbp.app_template_filter("mb")
def _mb(v):
    return f"{(v or 0) / 1024**2:.0f} MB"

def _agent(key):
    return agents.AGENTS.get(key) or abort(404)

def _pw():
    try:
        return ph.verify(current_user.password_hash, request.form.get("password", ""))
    except VerifyMismatchError:
        return False

def _html(html, trigger=None):
    r = make_response(html)
    if trigger:
        r.headers["HX-Trigger"] = trigger
    return r

def _msg(msg, ok, trigger=None):
    return _html(f'<p class="{"ok-t" if ok else "err"}">{escape(msg)}</p>', trigger)

def _call(a, method, path, timeout=10, **kw):
    try:
        r = agents.call(a, method, path, timeout=timeout, **kw)
        try:
            body = r.json()
        except ValueError:
            body = None
        return r.status_code, body, None
    except Exception as e:
        return 0, None, type(e).__name__

def _tabs_key():
    ags = list(agents.AGENTS.values())
    if not ags:
        abort(404)
    k = request.args.get("s")
    return ags, (k if k in agents.AGENTS else ags[0]["key"])

# ---------------- kontenery ----------------
@dbp.route("/docker")
@login_required
def docker_page():
    ags, key = _tabs_key()
    return render_template("docker.html", agents=ags, key=key)

@dbp.route("/partials/docker/<key>")
@login_required
def docker_partial(key):
    _agent(key)
    st = db.session.get(DockerState, key)
    cs = []
    for c in ((st.data or {}).get("containers", []) if st and st.data else []):
        c = dict(c); c["protected"] = c.get("project") in PROTECTED; c["cls"] = ds.pill_class(c)
        c["up_since"] = ds.parse_ts(c["started_at"]) if c["running"] else None
        cs.append(c)
    cs.sort(key=lambda c: (c.get("project") or "~", c["name"]))
    return render_template("_docker.html", key=key, st=st, cs=cs, now=now())

@dbp.route("/partials/docker/<key>/events")
@login_required
def docker_events(key):
    _agent(key)
    evs = ContainerEvent.query.filter_by(server=key).order_by(ContainerEvent.id.desc()).limit(40).all()
    return render_template("_events.html", evs=evs)

@dbp.post("/docker/<key>/c/<cid>/<act>")
@login_required
@limiter.limit("30/minute")
def c_action(key, cid, act):
    a = _agent(key)
    if not ID.match(cid) or act not in ("start", "stop", "restart"):
        abort(400)
    st = db.session.get(DockerState, key)
    c = next((c for c in (st.data or {}).get("containers", []) if c["id"] == cid), None) if st and st.data else None
    if not c:
        return _msg("Nie znaleziono kontenera, odśwież listę.", False)
    if act != "start" and c.get("project") in PROTECTED:
        return _msg(f"{c['name']} należy do panelu: zatrzymanie z panelu jest zablokowane.", False)
    code, body, err = _call(a, "POST", f"/docker/containers/{cid}/{act}", timeout=45)
    audit(f"docker {act} {key}/{c['name']} -> {code or err}")
    if code != 200:
        return _msg(f"Błąd: {(body or {}).get('error') or err or code}", False)
    ds.refresh(a, stats=False)
    return _msg(f"{c['name']}: {act} wykonane", True, "refresh-docker")

@dbp.get("/docker/<key>/c/<cid>/logs")
@login_required
def c_logs(key, cid):
    a = _agent(key)
    if not ID.match(cid):
        abort(400)
    tail = request.args.get("tail", "200")
    tail = int(tail) if tail.isdigit() else 200
    try:
        r = agents.call(a, "GET", f"/docker/containers/{cid}/logs?tail={tail}", timeout=20)
        body = r.text if r.status_code == 200 else f"Błąd agenta: {r.status_code}"
    except Exception as e:
        body = f"Błąd: {type(e).__name__}"
    return _html('<p class="muted">Logi (ostatnie linie) <button class="ghost sm" '
                 'onclick="this.parentNode.parentNode.innerHTML=\'\'">zamknij</button></p>'
                 f'<pre class="log">{escape(body)}</pre>')

@dbp.route("/api/docker/timeline")
@login_required
def api_timeline():
    key = request.args.get("server", "")
    _agent(key)
    hours = RANGES.get(request.args.get("range", "24h"), 24)
    end = now(); since = end - timedelta(hours=hours)
    kinds = ",".join(f"'{k}'" for k in ds.STATE_KINDS)
    prior = {r.name: r.state_after for r in db.session.execute(text(
        f"SELECT DISTINCT ON (name) name, state_after FROM container_events "
        f"WHERE server=:s AND ts < :since AND kind IN ({kinds}) ORDER BY name, ts DESC, id DESC"),
        {"s": key, "since": since})}
    evs = ContainerEvent.query.filter(ContainerEvent.server == key, ContainerEvent.ts >= since) \
        .order_by(ContainerEvent.ts, ContainerEvent.id).all()
    segs, marks = ds.build_timeline(prior, [(e.name, e.ts, e.kind, e.state_after) for e in evs], since, end)
    iso = lambda t: t.isoformat()
    rows = [{"name": n, "segs": [[iso(s), iso(e), st] for s, e, st in segs.get(n, [])],
             "marks": [[iso(t), k] for t, k in marks.get(n, [])]} for n in sorted(set(segs) | set(marks)) if segs.get(n)]
    return jsonify(**{"from": iso(since), "to": iso(end), "rows": rows})

# ---------------- stosy compose ----------------
@dbp.route("/stacks")
@login_required
def stacks_page():
    ags, key = _tabs_key()
    return render_template("stacks.html", agents=ags, key=key)

@dbp.route("/partials/stacks/<key>")
@login_required
def stacks_partial(key):
    code, body, err = _call(_agent(key), "GET", "/stacks", timeout=8)
    return render_template("_stacks.html", key=key, code=code, err=err, stacks=(body or {}).get("stacks", []))

@dbp.get("/stacks/<key>/<name>/edit")
@login_required
def st_edit(key, name):
    a = _agent(key)
    if not NAME.match(name):
        abort(400)
    kind = "env" if request.args.get("kind") == "env" else "compose"
    code, body, err = _call(a, "GET", f"/stacks/{name}/files/{kind}")
    if code != 200 or not body:
        return _msg(f"Nie udało się wczytać pliku: {err or code}", False)
    return render_template("_editor.html", key=key, name=name, kind=kind, **{k: body.get(k) for k in ("content", "exists", "file")})

@dbp.post("/stacks/<key>/<name>/save")
@login_required
@limiter.limit("10/minute")
def st_save(key, name):
    a = _agent(key)
    kind = "env" if request.form.get("kind") == "env" else "compose"
    if not NAME.match(name):
        abort(400)
    if not _pw():
        audit(f"stack save DENIED {key}/{name}")
        return _msg("Nieprawidłowe hasło.", False)
    code, body, err = _call(a, "PUT", f"/stacks/{name}/files/{kind}", timeout=40,
                            json={"content": request.form.get("content", "").replace("\r\n", "\n")})
    audit(f"stack save {key}/{name}/{kind} -> {code or err}")
    if code == 422:
        return _html(f'<p class="err">Walidacja nie przeszła, plik NIE został zapisany:</p><pre class="log">{escape((body or {}).get("error", ""))}</pre>')
    if code != 200 or not body or not body.get("ok"):
        return _msg(f"Błąd zapisu: {(body or {}).get('error') or err or code}", False)
    extra = " Kopia poprzedniej wersji zapisana (.bak)." if body.get("backup") else ""
    return _msg("Zapisano." + extra + " Użyj „Up”, aby zastosować zmiany.", True)

@dbp.post("/stacks/<key>/new")
@login_required
@limiter.limit("5/minute")
def st_new(key):
    a = _agent(key)
    name = request.form.get("name", "").strip().lower()
    if not re.match(r"^[a-z0-9][a-z0-9_-]{0,40}$", name):
        return _msg("Nazwa: małe litery, cyfry, - i _ (max 41 znaków).", False)
    if not _pw():
        audit(f"stack new DENIED {key}/{name}")
        return _msg("Nieprawidłowe hasło.", False)
    code, body, err = _call(a, "POST", "/stacks", timeout=40,
                            json={"name": name, "content": request.form.get("content", "").replace("\r\n", "\n")})
    audit(f"stack new {key}/{name} -> {code or err}")
    if code == 422:
        return _html(f'<p class="err">Walidacja nie przeszła:</p><pre class="log">{escape((body or {}).get("error", ""))}</pre>')
    if code != 200:
        return _msg(f"Błąd: {(body or {}).get('error') or err or code}", False)
    return _msg(f"Utworzono stos „{name}”. Kliknij „Up”, aby go uruchomić.", True, "refresh-stacks")

@dbp.post("/stacks/<key>/<name>/run/<action>")
@login_required
@limiter.limit("10/minute")
def st_run(key, name, action):
    a = _agent(key)
    if not NAME.match(name) or action not in ("up", "down", "pull", "restart"):
        abort(400)
    code, body, err = _call(a, "POST", f"/stacks/{name}/{action}")
    audit(f"stack {action} {key}/{name} -> {code or err}")
    if code != 200 or not body:
        return _html(f'<div id="job"><p class="err">{escape((body or {}).get("error") or err or code)}</p></div>')
    return render_template("_job.html", key=key, j={"id": body["job"], "stack": name, "action": action,
                                                     "status": "running", "output": "", "rc": None})

@dbp.get("/stacks/<key>/job/<jid>")
@login_required
def job(key, jid):
    if not ID.match(jid):
        abort(400)
    code, j, err = _call(_agent(key), "GET", f"/jobs/{jid}")
    if code != 200 or not j:
        return _html(f'<div id="job"><p class="err">Nie znaleziono zadania ({escape(err or code)})</p></div>')
    return _html(render_template("_job.html", key=key, j=j), None if j["status"] == "running" else "refresh-docker")
