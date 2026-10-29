from collections import defaultdict
from datetime import datetime, timezone
from . import agents
from .extensions import db
from .models import DockerState, ContainerEvent, now

STATE_KINDS = ("seen", "up", "stop", "crash", "gone")   # zdarzenia zmieniające stan na osi czasu

def parse_ts(s):
    if not s or s.startswith("0001"):
        return None
    s = s.rstrip("Z")
    if "." in s:
        base, frac = s.split(".", 1)
        s = f"{base}.{frac[:6]}"
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

def state_of(c):
    """up / crashed / stopped. Kody 0, 137, 143 traktujemy jako zatrzymanie celowe (chyba że OOM)."""
    if c["state"] == "running":
        return "up"
    if c["state"] == "restarting":
        return "crashed"
    if c["state"] in ("paused", "created"):
        return "stopped"
    if c.get("oom") or c.get("exit_code") not in (0, 137, 143, None):
        return "crashed"
    return "stopped"

def pill_class(c):
    return {"up": "ok", "crashed": "bad", "stopped": "gray"}[state_of(c)] if c["state"] != "paused" else "warn"

def _crash_detail(c):
    return "OOM (brak pamięci)" if c.get("oom") else f"kod wyjścia {c.get('exit_code')}"

def diff_events(prev, cur, first, t):
    P = {c["name"]: c for c in prev}
    names = {c["name"] for c in cur}
    out = []
    def add(c, kind, state, ts=None, detail=None):
        out.append(dict(name=c["name"], kind=kind, state=state, ts=ts or t, code=c.get("exit_code"), detail=detail))
    for c in cur:
        p = P.get(c["name"]); s = state_of(c)
        if p is None:
            add(c, "seen", s, detail=None if first else "nowy kontener")
            continue
        ps = state_of(p)
        if s != ps:
            if s == "up":
                add(c, "up", s, parse_ts(c["started_at"]))
            elif s == "crashed":
                add(c, "crash", s, parse_ts(c["finished_at"]), _crash_detail(c))
            else:
                add(c, "stop", s, parse_ts(c["finished_at"]), f"kod wyjścia {c.get('exit_code')}")
        elif c["restarts"] > p["restarts"] or (s == "up" and c["started_at"] != p["started_at"]):
            add(c, "restart", s, parse_ts(c["started_at"]), f"poprzedni kod wyjścia {c.get('exit_code')}")
        if c.get("oom") and not p.get("oom"):
            add(c, "oom", s, parse_ts(c["finished_at"]), "zabity przez OOM")
        if c.get("health") != p.get("health"):
            if c.get("health") == "unhealthy":
                add(c, "unhealthy", s)
            elif p.get("health") == "unhealthy" and c.get("health") == "healthy":
                add(c, "healthy", s)
    for p in prev:
        if p["name"] not in names:
            add(p, "gone", "gone", detail="usunięty")
    return out

def build_timeline(prior, events, since, end):
    """prior {nazwa: stan przed `since`}, events [(nazwa, ts, kind, stan)] posortowane. -> (segs, marks)"""
    cur = {n: (s, since) for n, s in prior.items()}
    segs, marks = defaultdict(list), defaultdict(list)
    for name, ts, kind, state in events:
        if kind in STATE_KINDS:
            s0, t0 = cur.get(name, (None, since))
            ts = max(ts, t0)
            if s0 and s0 != "gone" and ts > t0:
                segs[name].append((t0, ts, s0))
            cur[name] = (state, ts)
        else:
            marks[name].append((ts, kind))
    for name, (s0, t0) in cur.items():
        if s0 and s0 != "gone" and end > t0:
            segs[name].append((t0, end, s0))
    return segs, marks

def refresh(a, stats=True):
    """Pobiera kontenery z agenta, zapisuje stan i zdarzenia. Zwraca True przy sukcesie."""
    cs, err = None, None
    try:
        cs = agents.containers(a, stats)
    except Exception as e:
        resp = getattr(e, "response", None)
        err = f"{type(e).__name__}" + (f" {resp.status_code}" if resp is not None else "")
    st = db.session.get(DockerState, a["key"]) or DockerState(server=a["key"])
    st.checked = now()
    if cs is None:
        st.ok, st.error = False, err
    else:
        prev = (st.data or {}).get("containers", [])
        pm = {c["name"]: c for c in prev}
        for c in cs:                     # odświeżenie bez statystyk nie kasuje ostatnich CPU/RAM
            p = pm.get(c["name"])
            if "cpu" not in c and p and c["running"] and "cpu" in p:
                c["cpu"], c["mem"], c["mem_limit"] = p["cpu"], p["mem"], p["mem_limit"]
        for e in diff_events(prev, cs, st.data is None, now()):
            db.session.add(ContainerEvent(server=a["key"], name=e["name"], ts=e["ts"], kind=e["kind"],
                                          state_after=e["state"], exit_code=e["code"], detail=e["detail"]))
        st.ok, st.error, st.data = True, None, {"containers": cs}
    db.session.add(st)
    db.session.commit()
    return cs is not None
