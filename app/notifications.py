"""Ekran „Powiadomienia”: subskrypcje push, progi alertów, historia. JSON API wołane z frontendu (React)."""
from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required
from .extensions import db, limiter
from . import alerts, push
from .models import PushSubscription, now
from .routes import audit

nbp = Blueprint("notif", __name__)


def _err(msg, code=400):
    r = jsonify(error=msg); r.status_code = code
    return r


def ua_short(ua):
    """Z User-Agenta robimy krótką nazwę urządzenia, np. „Chrome, Android”."""
    ua = ua or ""
    os_ = next((n for k, n in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
                               ("Mac OS X", "macOS"), ("Linux", "Linux")) if k in ua), "?")
    br = next((n for k, n in (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("CriOS", "Chrome"),
                              ("Chrome/", "Chrome"), ("Safari/", "Safari")) if k in ua), "przeglądarka")
    return f"{br}, {os_}"


_iso = lambda t: t.isoformat() if t else None


@nbp.get("/api/notifications")
@login_required
def page():
    subs = PushSubscription.query.filter_by(user_id=current_user.id).order_by(PushSubscription.created).all()
    return jsonify(
        configured=push.configured(),
        settings=alerts.get_settings(),
        limits={k: list(v) for k, v in alerts.LIMITS.items()},
        subs=[dict(id=s.id, device=ua_short(s.ua), created=_iso(s.created), last_ok=_iso(s.last_ok)) for s in subs],
        active=[dict(since=_iso(a.since), title=a.title, detail=a.detail) for a in alerts.active_alerts()],
        events=[dict(ts=_iso(e.ts), kind=e.kind, title=e.title, detail=e.detail) for e in alerts.recent_events(20)])


def _num(j, name, errors):
    lo, hi = alerts.LIMITS[name]
    try:
        v = int(j.get(name))
        if isinstance(j.get(name), bool):
            raise ValueError
    except (TypeError, ValueError):
        errors.append(f"{name}: podaj liczbę całkowitą"); return alerts.DEFAULTS[name]
    if not lo <= v <= hi:
        errors.append(f"{name}: dozwolony zakres {lo}–{hi}"); return alerts.DEFAULTS[name]
    return v


@nbp.post("/api/notifications/settings")
@login_required
@limiter.limit("20/minute")
def save_settings():
    j = request.get_json(silent=True) or {}
    errors, cfg = [], {}
    for k in alerts.FLAGS:
        cfg[k] = j.get(k) is True
    for k in alerts.LIMITS:
        cfg[k] = _num(j, k, errors)
    if errors:
        return _err("Nie zapisano: " + "; ".join(errors))
    alerts.save_settings(cfg)
    audit("alert settings: " + ", ".join(f"{k}={cfg[k]}" for k in sorted(cfg)))
    return jsonify(ok=True, message="Zapisano ustawienia alertów.", settings=alerts.get_settings())

@nbp.get("/api/push/key")
@login_required
def api_key():
    return jsonify(configured=push.configured(), key=push.public_key() if push.configured() else None)


@nbp.post("/api/push/subscribe")
@login_required
@limiter.limit("30/minute")
def api_subscribe():
    j = request.get_json(silent=True) or {}
    ep, keys = j.get("endpoint"), j.get("keys") or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if not (isinstance(ep, str) and isinstance(p256dh, str) and isinstance(auth, str)):
        return _err("Nieprawidłowa subskrypcja")
    if len(ep) > 1000 or len(p256dh) > 200 or len(auth) > 100:
        return _err("Nieprawidłowa subskrypcja")
    if not push.endpoint_allowed(ep):
        audit(f"push subscribe DENIED (endpoint spoza listy): {ep[:80]}")
        return _err("Ten adres usługi push nie jest dozwolony (PUSH_ALLOWED_HOSTS).", 403)
    sub = PushSubscription.query.filter_by(endpoint=ep).first()
    new = sub is None
    if new:
        sub = PushSubscription(endpoint=ep)
    sub.user_id, sub.p256dh, sub.auth = current_user.id, p256dh, auth
    sub.ua = (request.headers.get("User-Agent") or "")[:200]
    db.session.add(sub); db.session.commit()
    if new:
        audit("push subscribe")
    return jsonify(ok=True)


@nbp.post("/api/push/unsubscribe")
@login_required
def api_unsubscribe():
    ep = (request.get_json(silent=True) or {}).get("endpoint")
    n = PushSubscription.query.filter_by(endpoint=ep, user_id=current_user.id).delete() if isinstance(ep, str) else 0
    db.session.commit()
    if n:
        audit("push unsubscribe")
    return jsonify(ok=True)


@nbp.post("/api/push/delete")
@login_required
def api_delete():
    sid = (request.get_json(silent=True) or {}).get("id")
    sub = db.session.get(PushSubscription, sid) if isinstance(sid, int) else None
    if sub is None or sub.user_id != current_user.id:
        abort(404)
    db.session.delete(sub); db.session.commit()
    audit("push device removed")
    return jsonify(ok=True)


@nbp.post("/api/push/test")
@login_required
@limiter.limit("5/minute")
def api_test():
    if not push.configured():
        return _err("Brak kluczy VAPID w konfiguracji serwera.", 409)
    sent = push.send("Test powiadomień", "Jeśli to widzisz, alerty z panelu będą docierać na to urządzenie.",
                     tag="test", url="/notifications", user_id=current_user.id)
    audit(f"push test (dostarczono: {sent})")
    return jsonify(sent=sent)
