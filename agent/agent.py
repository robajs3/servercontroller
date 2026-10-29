"""Agent metryk. Działa na hoście (systemd), nie w kontenerze. Etap 5 doda Dockera."""
import hmac, os, platform, shutil, subprocess, threading, time
import psutil
from flask import Flask, jsonify, request, abort

TOKEN = os.environ["AGENT_TOKEN"].encode()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024
_cpu = {"total": 0.0, "per": []}

def _sampler():
    psutil.cpu_percent(None); psutil.cpu_percent(None, percpu=True)
    while True:
        time.sleep(2)
        _cpu["total"] = psutil.cpu_percent(None)
        _cpu["per"] = psutil.cpu_percent(None, percpu=True)
threading.Thread(target=_sampler, daemon=True).start()

def cpu_model():
    found = {}
    try:
        for line in open("/proc/cpuinfo"):
            k, _, v = line.partition(":")
            found.setdefault(k.strip(), v.strip())   # x86: "model" to numer, nazwa jest w "model name"
    except OSError:
        pass
    for key in ("model name", "Hardware", "Model"):   # kolejność ma znaczenie (Pi: "Model")
        if found.get(key):
            return found[key]
    return platform.processor() or platform.machine()

def os_name():
    try:
        return platform.freedesktop_os_release().get("PRETTY_NAME", platform.system())
    except OSError:
        return platform.system()

SKIP_FS = {"squashfs", "tmpfs", "devtmpfs", "overlay", "proc", "sysfs", "cgroup2", "efivarfs", "ramfs"}
SKIP_MP = ("/snap", "/var/lib/docker", "/run", "/sys", "/proc")

def disks():
    seen, out = set(), []
    for p in psutil.disk_partitions(all=False):
        if p.fstype in SKIP_FS or p.device in seen or p.device.startswith("/dev/loop") or p.mountpoint.startswith(SKIP_MP):
            continue
        seen.add(p.device)
        try:
            u = psutil.disk_usage(p.mountpoint)
        except OSError:
            continue
        out.append({"mount": p.mountpoint, "device": p.device, "fstype": p.fstype,
                    "total": u.total, "used": u.used, "percent": u.percent})
    return out

CPU_CHIPS = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal", "acpitz")

def temps():
    if not hasattr(psutil, "sensors_temperatures"):
        return [], None
    flat, cpu = [], []
    for chip, items in (psutil.sensors_temperatures() or {}).items():
        for t in items:
            if t.current is None:
                continue
            flat.append({"chip": chip, "label": t.label or chip, "current": t.current})
            if chip in CPU_CHIPS:
                cpu.append(t.current)
    pool = cpu or [t["current"] for t in flat]
    return flat, (max(pool) if pool else None)

def gpus():
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3).stdout
        res = []
        for line in out.strip().splitlines():
            n, u, mu, mt, t = [x.strip() for x in line.split(",")]
            res.append({"name": n, "util": float(u), "mem_used": float(mu) * 2**20,
                        "mem_total": float(mt) * 2**20, "temp": float(t)})
        return res
    except Exception:
        return []

def net():
    rx = tx = 0
    for nic, c in psutil.net_io_counters(pernic=True).items():
        if nic == "lo" or nic.startswith(("veth", "docker", "br-")):
            continue
        rx += c.bytes_recv; tx += c.bytes_sent
    return {"rx": rx, "tx": tx}

@app.before_request
def _auth():
    if request.path == "/health":
        return
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer ") or not hmac.compare_digest(h[7:].encode(), TOKEN):
        abort(403)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/metrics")
def metrics():
    vm, sw = psutil.virtual_memory(), psutil.swap_memory()
    used = vm.total - vm.available
    freq = psutil.cpu_freq()
    tlist, tmax = temps()
    return jsonify({
        "ts": time.time(), "hostname": platform.node(), "os": os_name(),
        "uptime": time.time() - psutil.boot_time(),
        "cpu": {"model": cpu_model(), "cores": psutil.cpu_count(logical=False) or psutil.cpu_count(),
                "threads": psutil.cpu_count(), "percent": _cpu["total"], "per_core": _cpu["per"],
                "freq_mhz": freq.current if freq else None, "load": list(os.getloadavg())},
        "mem": {"total": vm.total, "used": used, "percent": used / vm.total * 100,
                "swap_total": sw.total, "swap_used": sw.used},
        "disks": disks(), "temps": tlist, "temp_max": tmax, "net": net(), "gpus": gpus(),
    })

try:
    from dockerapi import bp as _docker_bp
    app.register_blueprint(_docker_bp)
except ImportError as e:   # brak pakietu `docker`: reszta agenta działa
    print("API Dockera wyłączone:", e)
