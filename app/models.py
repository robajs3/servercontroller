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

from sqlalchemy.dialects.postgresql import JSONB

class AgentState(db.Model):                               # ostatni znany stan agenta
    __tablename__ = "agent_state"
    server = db.Column(db.String(32), primary_key=True)
    checked = db.Column(db.DateTime(timezone=True))
    last_ok = db.Column(db.DateTime(timezone=True))
    ok = db.Column(db.Boolean, default=False)
    error = db.Column(db.String(120))
    data = db.Column(JSONB)

class MetricSample(db.Model):
    __tablename__ = "metric_samples"
    id = db.Column(db.BigInteger, primary_key=True)
    server = db.Column(db.String(32), nullable=False)
    ts = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    cpu = db.Column(db.Float)
    ram_used = db.Column(db.BigInteger)
    ram_total = db.Column(db.BigInteger)
    temp = db.Column(db.Float)
    rx_bps = db.Column(db.Float)
    tx_bps = db.Column(db.Float)
    __table_args__ = (db.Index("ix_ms_server_ts", "server", "ts"),)

class MetricAgg(db.Model):                                # średnie minutowe
    __tablename__ = "metric_agg"
    server = db.Column(db.String(32), primary_key=True)
    bucket = db.Column(db.DateTime(timezone=True), primary_key=True)
    cpu_avg = db.Column(db.Float)
    cpu_max = db.Column(db.Float)
    ram_pct = db.Column(db.Float)
    temp_max = db.Column(db.Float)
    n = db.Column(db.Integer, nullable=False)

class DockerState(db.Model):                              # ostatni znany stan kontenerów
    __tablename__ = "docker_state"
    server = db.Column(db.String(32), primary_key=True)
    checked = db.Column(db.DateTime(timezone=True))
    ok = db.Column(db.Boolean, default=False)
    error = db.Column(db.String(160))
    data = db.Column(JSONB)

class ContainerEvent(db.Model):
    __tablename__ = "container_events"
    id = db.Column(db.BigInteger, primary_key=True)
    server = db.Column(db.String(32), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    ts = db.Column(db.DateTime(timezone=True), nullable=False)
    kind = db.Column(db.String(16), nullable=False)       # seen up stop crash restart oom unhealthy healthy gone
    state_after = db.Column(db.String(16), nullable=False)  # up crashed stopped gone
    exit_code = db.Column(db.Integer)
    detail = db.Column(db.String(200))
    __table_args__ = (db.Index("ix_ce_server_ts", "server", "ts"),)
