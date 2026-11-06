import os
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import text
from .extensions import db, limiter
from .security import verify_totp_once, is_locked, register_failure, reset_failures, LOCK_MINUTES
from .models import User, AuditLog, PingSample, StatusEvent, AgentState, now
from . import actions, agents
from flask import abort

bp = Blueprint("main", __name__)
ph = PasswordHasher()
DUMMY = ph.hash("dummy-password")

def audit(action):
    db.session.add(AuditLog(user=getattr(current_user, "username", None),
                            ip=request.remote_addr, action=action))
    db.session.commit()

def _res(msg, ok, code=None):
    """Wspólna odpowiedź akcji: {ok, message}. Błędy dostają kod 4xx, żeby klient nie musiał zgadywać."""
    r = jsonify(ok=ok, message=msg)
    r.status_code = code or (200 if ok else 400)
    return r

@bp.post("/api/login")
@limiter.limit("5/minute;30/hour")
def login():
    j = request.get_json(silent=True) or {}
    name = str(j.get("username", ""))
    u = User.query.filter_by(username=name).first()
    locked = bool(u and is_locked(u))
    try:                                      # hasło sprawdzamy zawsze (stały czas, także dla nieznanego loginu)
        ph.verify(u.password_hash if u else DUMMY, str(j.get("password", "")))
        pw_ok = u is not None
    except VerifyMismatchError:
        pw_ok = False
    # kod TOTP zużywamy dopiero po poprawnym haśle i tylko gdy konto nie jest zablokowane
    if pw_ok and not locked and verify_totp_once(u, str(j.get("code", ""))):
        reset_failures(u)
        login_user(u, remember=False)
        audit("login ok")
        return jsonify(ok=True)
    newly_locked = bool(u and not locked and register_failure(u))
    audit(f"login FAIL ({name[:32]})" + (" [konto zablokowane]" if locked else "")
          + (f" -> blokada {LOCK_MINUTES} min" if newly_locked else ""))
    return _res("Nieprawidłowe dane logowania lub konto jest tymczasowo zablokowane", False, 401)

@bp.post("/api/logout")
@login_required
def logout():
    audit("logout"); logout_user()
    return jsonify(ok=True)

@bp.route("/api/status")
@login_required
def status():
    last = PingSample.query.order_by(PingSample.id.desc()).first()
    ev = StatusEvent.query.order_by(StatusEvent.id.desc()).first()
    stale = last is None or (now() - last.ts) > timedelta(seconds=3 * int(os.getenv("PING_INTERVAL", 10)) + 5)
    return jsonify(stale=stale, host=os.getenv("MAIN_HOST"),
                   state=ev.state if ev else None, since=ev.ts.isoformat() if ev else None,
                   icmp_ok=bool(last and last.ok), icmp_ms=last.rtt_ms if last else None,
                   tcp_ok=bool(last and last.tcp_ok), tcp_ms=last.tcp_ms if last else None)

RANGES = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}
# uwaga: alias kolumny nie może nazywać się `t` (koliduje z Row.t w SQLAlchemy 2.0)
RAW_SQL = """SELECT to_timestamp(floor(extract(epoch from ts)/:s)*:s) AS bucket,
  avg(rtt_ms) FILTER (WHERE ok) rtt, max(rtt_ms) mx,
  100.0*avg((NOT ok)::int) loss
  FROM ping_samples WHERE ts > :since GROUP BY 1 ORDER BY 1"""
AGG_SQL = """SELECT to_timestamp(floor(extract(epoch from bucket)/:s)*:s) AS bucket,
  sum(avg_rtt*n_ok)/NULLIF(sum(n_ok),0) rtt, max(max_rtt) mx,
  100.0*(sum(n)-sum(n_ok))/sum(n) loss
  FROM ping_agg WHERE bucket > :since GROUP BY 1 ORDER BY 1"""

@bp.route("/api/ping")
@login_required
def api_ping():
    rng = request.args.get("range", "1h")
    hours = RANGES.get(rng, 1)
    step = max(int(hours * 3600 / 300), 10)
    raw = hours <= 24
    if not raw:
        step = max(step, 60)
    rows = db.session.execute(text(RAW_SQL if raw else AGG_SQL),
                              {"s": step, "since": now() - timedelta(hours=hours)}).all()
    return jsonify([{"t": r.bucket.isoformat(),
                     "rtt": round(r.rtt, 2) if r.rtt is not None else None,
                     "max": round(r.mx, 2) if r.mx is not None else None,
                     "loss": round(float(r.loss), 1)} for r in rows])

def _last_state():
    ev = StatusEvent.query.order_by(StatusEvent.id.desc()).first()
    return ev.state if ev else None

@bp.post("/api/actions/wake")
@login_required
@limiter.limit("5/minute")
def act_wake():
    if _last_state() == "ONLINE":
        return _res("Serwer już działa.", False)
    try:
        actions.wake()
    except Exception as e:
        audit(f"wake FAIL: {type(e).__name__}")
        return _res("Nie udało się wysłać pakietu WoL (usługa wol).", False)
    db.session.add(StatusEvent(state="BOOTING")); db.session.commit()
    audit("wake")
    return _res("Wysłano magic packet. Czekam na start serwera…", True)

@bp.post("/api/actions/shutdown")
@login_required
@limiter.limit("3/minute")
def act_shutdown():
    pw = str((request.get_json(silent=True) or {}).get("password", ""))
    try:
        ph.verify(current_user.password_hash, pw)
    except VerifyMismatchError:
        audit("shutdown DENIED (zle haslo)")
        return _res("Nieprawidłowe hasło.", False)
    try:
        actions.shutdown()
    except Exception as e:
        audit(f"shutdown FAIL: {type(e).__name__}: {str(e)[:120]}")
        return _res(f"Nie udało się wyłączyć: {type(e).__name__}", False)
    db.session.add(StatusEvent(state="SHUTTING_DOWN")); db.session.commit()
    audit("shutdown")
    return _res("Wysłano polecenie wyłączenia.", True)

@bp.route("/api/servers/<key>")
@login_required
def server_card(key):
    a = agents.AGENTS.get(key) or abort(404)
    st = db.session.get(AgentState, key)
    iso = lambda t: t.isoformat() if t else None
    return jsonify(key=key, name=a["name"],
                   state=None if not st else dict(ok=bool(st.ok), error=st.error, checked=iso(st.checked),
                                                  last_ok=iso(st.last_ok), data=st.data))

M_RAW = """SELECT to_timestamp(floor(extract(epoch from ts)/:s)*:s) AS bucket, avg(cpu) cpu,
  avg(100.0*ram_used/NULLIF(ram_total,0)) ram, max(temp) temp
  FROM metric_samples WHERE server=:srv AND ts > :since GROUP BY 1 ORDER BY 1"""
M_AGG = """SELECT to_timestamp(floor(extract(epoch from bucket)/:s)*:s) AS bucket,
  sum(cpu_avg*n)/sum(n) cpu, sum(ram_pct*n)/sum(n) ram, max(temp_max) temp
  FROM metric_agg WHERE server=:srv AND bucket > :since GROUP BY 1 ORDER BY 1"""

@bp.route("/api/metrics")
@login_required
def api_metrics():
    srv = request.args.get("server", "")
    if srv not in agents.AGENTS:
        abort(404)
    hours = RANGES.get(request.args.get("range", "1h"), 1)
    raw = hours <= 24
    step = max(int(hours * 3600 / 300), 10 if raw else 60)
    rows = db.session.execute(text(M_RAW if raw else M_AGG),
        {"s": step, "srv": srv, "since": now() - timedelta(hours=hours)}).all()
    r1 = lambda v: round(float(v), 1) if v is not None else None
    return jsonify([{"t": r.bucket.isoformat(), "cpu": r1(r.cpu), "ram": r1(r.ram), "temp": r1(r.temp)} for r in rows])
