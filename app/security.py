import hmac, time
import pyotp
from sqlalchemy import or_, update
from .extensions import db
from .models import User

def verify_totp_once(user, code):
    """Kod TOTP można zużyć tylko raz. Zapamiętujemy krok czasowy (30 s) ostatnio użytego kodu
    i odrzucamy kody z tego samego lub wcześniejszego kroku (ochrona przed replay).
    Zapis jest atomowy (UPDATE ... WHERE last_totp_step < krok), więc dwa równoległe żądania
    z tym samym kodem nie przejdą oba."""
    code = (code or "").strip()
    if len(code) != 6 or not code.isdigit():
        return False
    totp, step = pyotp.TOTP(user.totp_secret), int(time.time() // 30)
    for s in (step - 1, step, step + 1):               # tolerancja zegara ±30 s
        if hmac.compare_digest(totp.at(s * 30), code):
            res = db.session.execute(update(User).where(
                User.id == user.id, or_(User.last_totp_step.is_(None), User.last_totp_step < s)
            ).values(last_totp_step=s))
            db.session.commit()
            return res.rowcount == 1
    return False

# --- blokada konta po serii błędnych logowań (uzupełnia limit per IP) ---
import os
from datetime import timedelta
from .models import now

MAX_FAILED = int(os.getenv("LOGIN_MAX_FAILED", 5))
LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", 10))

def is_locked(user):
    return bool(user.locked_until and user.locked_until > now())

def register_failure(user):
    """Zlicza błąd; po MAX_FAILED błędach blokuje konto na LOCK_MINUTES. Zwraca True, gdy zablokowano."""
    user.failed_count = (user.failed_count or 0) + 1
    locked = user.failed_count >= MAX_FAILED
    if locked:
        user.locked_until = now() + timedelta(minutes=LOCK_MINUTES)
        user.failed_count = 0
    db.session.commit()
    return locked

def reset_failures(user):
    user.failed_count, user.locked_until = 0, None
    db.session.commit()
