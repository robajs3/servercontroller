"""Wysyłka powiadomień Web Push (VAPID). Używana przez workera (alerty) i przez web (test)."""
import base64, json, logging, os
from urllib.parse import urlparse
from .extensions import db
from .models import PushSubscription, now

log = logging.getLogger("push")

# Serwer sam wykonuje POST na adres `endpoint` podany przez przeglądarkę, więc bez listy dozwolonych
# hostów zalogowany użytkownik mógłby skierować go na dowolny adres (SSRF, np. do agenta w sieci domowej).
# Domyślnie: usługi push Chrome/Edge/Opera (FCM), Firefoksa, Safari/iOS i Windows.
PUSH_HOSTS = (
    "fcm.googleapis.com",
    ".push.services.mozilla.com",
    ".push.apple.com",
    ".notify.windows.com",
)

def _extra_hosts():
    return tuple(h.strip().lower() for h in os.getenv("PUSH_ALLOWED_HOSTS", "").split(",") if h.strip())

def endpoint_allowed(url):
    try:
        u = urlparse(url)
        host = (u.hostname or "").lower()
    except ValueError:
        return False
    if u.scheme != "https" or not host or u.username or u.password or u.port not in (None, 443):
        return False
    for h in PUSH_HOSTS + _extra_hosts():
        if (h.startswith(".") and host.endswith(h)) or host == h.lstrip("."):
            return True
    return False

def _b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def generate_keys():
    """Nowa para kluczy VAPID: (prywatny, publiczny) jako base64url do wklejenia do .env."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from py_vapid import Vapid
    v = Vapid(); v.generate_keys()
    priv = v.private_key.private_numbers().private_value.to_bytes(32, "big")
    pub = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return _b64u(priv), _b64u(pub)

def public_key():
    return os.getenv("VAPID_PUBLIC_KEY", "").strip()

def configured():
    return bool(public_key() and os.getenv("VAPID_PRIVATE_KEY") and os.getenv("VAPID_SUBJECT"))

def _send_one(sub, payload, ttl, urgency):
    from pywebpush import webpush, WebPushException
    try:
        webpush(subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                data=payload, vapid_private_key=os.environ["VAPID_PRIVATE_KEY"].strip(),
                vapid_claims={"sub": os.environ["VAPID_SUBJECT"].strip()},   # świeży słownik: biblioteka go modyfikuje
                ttl=ttl, headers={"Urgency": urgency}, timeout=8)
        return "ok"
    except WebPushException as e:
        code = getattr(e.response, "status_code", None)
        if code in (404, 410):                       # subskrypcja wygasła lub została cofnięta w przeglądarce
            return "gone"
        log.warning("push do #%s nieudany: %s", sub.id, str(e)[:200])
        return "error"
    except Exception as e:                           # sieć, zły klucz itp. nie mogą zatrzymać workera
        log.warning("push do #%s nieudany: %s", sub.id, type(e).__name__)
        return "error"

def send(title, body, tag, url="/", urgent=False, user_id=None):
    """Wysyła powiadomienie na wszystkie (lub wybranego użytkownika) urządzenia. Zwraca liczbę dostarczonych."""
    if not configured():
        return 0
    q = PushSubscription.query
    if user_id is not None:
        q = q.filter_by(user_id=user_id)
    payload = json.dumps({"title": title, "body": body, "tag": tag, "url": url, "urgent": urgent})
    sent = 0
    for sub in q.all():
        res = _send_one(sub, payload, ttl=3600 if urgent else 600, urgency="high" if urgent else "normal")
        if res == "ok":
            sub.last_ok = now(); sent += 1
        elif res == "gone":
            db.session.delete(sub)
    db.session.commit()
    return sent
