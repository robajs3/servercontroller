import os, socket, time, logging
from datetime import timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from icmplib import ping
from sqlalchemy import text
from . import create_app
from .extensions import db
from .models import PingSample, StatusEvent, now

log = logging.getLogger("worker"); logging.basicConfig(level=logging.INFO)
HOST = os.environ["MAIN_HOST"]
TCP_PORT = int(os.getenv("MAIN_TCP_PORT", 22))
INTERVAL = int(os.getenv("PING_INTERVAL", 10))
THRESHOLD = int(os.getenv("FAIL_THRESHOLD", 3))
RAW_DAYS = max(int(os.getenv("RETENTION_DAYS_RAW", 2)), 1)
AGG_DAYS = int(os.getenv("RETENTION_DAYS_AGG", 30))

app = create_app()
fails = 0
BOOT_TIMEOUT = int(os.getenv("BOOT_TIMEOUT", 300))
SHUTDOWN_TIMEOUT = int(os.getenv("SHUTDOWN_TIMEOUT", 120))

def probe():
    r = ping(HOST, count=1, timeout=1, privileged=False)
    icmp_ok, rtt = r.is_alive, (r.avg_rtt if r.is_alive else None)
    t0 = time.perf_counter()
    try:
        socket.create_connection((HOST, TCP_PORT), timeout=1).close()
        tcp_ok, tcp_ms = True, (time.perf_counter() - t0) * 1000
    except OSError:
        tcp_ok, tcp_ms = False, None
    return icmp_ok, rtt, tcp_ok, tcp_ms

def tick():
    global fails
    try:
        icmp_ok, rtt, tcp_ok, tcp_ms = probe()
        alive = icmp_ok or tcp_ok
        with app.app_context():
            db.session.add(PingSample(ok=icmp_ok, rtt_ms=rtt, tcp_ok=tcp_ok, tcp_ms=tcp_ms))
            fails = 0 if alive else fails + 1
            last = StatusEvent.query.order_by(StatusEvent.id.desc()).first()  # web też zapisuje zdarzenia
            state = last.state if last else None
            age = (now() - last.ts).total_seconds() if last else 0
            new = state
            if state == "BOOTING":
                if alive: new = "ONLINE"
                elif age > BOOT_TIMEOUT: new = "OFFLINE"        # nie wstał
            elif state == "SHUTTING_DOWN":
                if fails >= THRESHOLD: new = "OFFLINE"
                elif age > SHUTDOWN_TIMEOUT: new = "ONLINE"     # nie wyłączył się
            elif alive: new = "ONLINE"
            elif fails >= THRESHOLD: new = "OFFLINE"
            if new and new != state:
                db.session.add(StatusEvent(state=new))
                log.info("Zmiana stanu: %s -> %s", state, new)  # etap 5: push
            db.session.commit()
    except Exception:
        log.exception("tick failed")

def maintenance():
    try:
        with app.app_context():
            db.session.execute(text("""
              INSERT INTO ping_agg(bucket, avg_rtt, max_rtt, n, n_ok)
              SELECT date_trunc('minute', ts), avg(rtt_ms) FILTER (WHERE ok), max(rtt_ms),
                     count(*), count(*) FILTER (WHERE ok)
              FROM ping_samples
              WHERE ts >= :since AND ts < date_trunc('minute', now()) GROUP BY 1
              ON CONFLICT (bucket) DO UPDATE SET avg_rtt=EXCLUDED.avg_rtt,
                max_rtt=EXCLUDED.max_rtt, n=EXCLUDED.n, n_ok=EXCLUDED.n_ok"""),
                {"since": now() - timedelta(hours=2)})
            db.session.execute(text("DELETE FROM ping_samples WHERE ts < :c"),
                               {"c": now() - timedelta(days=RAW_DAYS)})
            db.session.execute(text("DELETE FROM ping_agg WHERE bucket < :c"),
                               {"c": now() - timedelta(days=AGG_DAYS)})
            db.session.commit()
    except Exception:
        log.exception("maintenance failed")

if __name__ == "__main__":
    time.sleep(8)  # poczekaj aż web utworzy tabele
    s = BlockingScheduler(timezone="UTC")
    s.add_job(tick, "interval", seconds=INTERVAL, max_instances=1, coalesce=True)
    s.add_job(maintenance, "interval", minutes=10, max_instances=1)
    s.start()
