import os
from datetime import timedelta
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import text
from .extensions import db, limiter
from .models import User, AuditLog, PingSample, StatusEvent, now

bp = Blueprint("main", __name__)
ph = PasswordHasher()
DUMMY = ph.hash("dummy-password")

def audit(action):
    db.session.add(AuditLog(user=getattr(current_user, "username", None),
                            ip=request.remote_addr, action=action))
    db.session.commit()

@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5/minute;30/hour", methods=["POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username", "")).first()
        ok = False
        try:
            ph.verify(u.password_hash if u else DUMMY, request.form.get("password", ""))
            ok = u is not None
        except VerifyMismatchError:
            pass
        code = request.form.get("code", "").strip()
        if ok and pyotp.TOTP(u.totp_secret).verify(code, valid_window=1):
            login_user(u, remember=False)
            audit("login ok")
            return redirect(url_for("main.dashboard"))
        audit(f"login FAIL ({request.form.get('username','')[:32]})")
        flash("Nieprawidłowe dane logowania")
    return render_template("login.html")

@bp.post("/logout")
@login_required
def logout():
    audit("logout"); logout_user()
    return redirect(url_for("main.login"))

@bp.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")

@bp.route("/partials/status")
@login_required
def status():
    last = PingSample.query.order_by(PingSample.id.desc()).first()
    ev = StatusEvent.query.order_by(StatusEvent.id.desc()).first()
    stale = last is None or (now() - last.ts) > timedelta(seconds=3 * int(os.getenv("PING_INTERVAL", 10)) + 5)
    return render_template("_status.html", last=last, ev=ev, stale=stale,
                           host=os.getenv("MAIN_HOST"))

RANGES = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}
RAW_SQL = """SELECT to_timestamp(floor(extract(epoch from ts)/:s)*:s) t,
  avg(rtt_ms) FILTER (WHERE ok) rtt, max(rtt_ms) mx,
  100.0*avg((NOT ok)::int) loss
  FROM ping_samples WHERE ts > :since GROUP BY 1 ORDER BY 1"""
AGG_SQL = """SELECT to_timestamp(floor(extract(epoch from bucket)/:s)*:s) t,
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
    return jsonify([{"t": r.t.isoformat(),
                     "rtt": round(r.rtt, 2) if r.rtt is not None else None,
                     "max": round(r.mx, 2) if r.mx is not None else None,
                     "loss": round(float(r.loss), 1)} for r in rows])
