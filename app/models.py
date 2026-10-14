from datetime import datetime, timezone
from flask_login import UserMixin
from .extensions import db

def now():
    return datetime.now(timezone.utc)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    totp_secret = db.Column(db.String(64), nullable=False)

class PingSample(db.Model):
    __tablename__ = "ping_samples"
    id = db.Column(db.BigInteger, primary_key=True)
    ts = db.Column(db.DateTime(timezone=True), default=now, index=True, nullable=False)
    ok = db.Column(db.Boolean, nullable=False)          # ICMP
    rtt_ms = db.Column(db.Float)
    tcp_ok = db.Column(db.Boolean, nullable=False)
    tcp_ms = db.Column(db.Float)

class PingAgg(db.Model):                                  # średnie minutowe
    __tablename__ = "ping_agg"
    bucket = db.Column(db.DateTime(timezone=True), primary_key=True)
    avg_rtt = db.Column(db.Float)
    max_rtt = db.Column(db.Float)
    n = db.Column(db.Integer, nullable=False)
    n_ok = db.Column(db.Integer, nullable=False)

class StatusEvent(db.Model):
    __tablename__ = "status_events"
    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime(timezone=True), default=now, index=True, nullable=False)
    state = db.Column(db.String(16), nullable=False)    # ONLINE / OFFLINE

class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    user = db.Column(db.String(64))
    ip = db.Column(db.String(64))
    action = db.Column(db.String(255), nullable=False)
