"""Testy silnika alertów i bezpieczeństwa push.
Część czysta (maszyna stanów, lista hostów) działa bez bazy. Testy integracyjne wymagają osobnej, pustej bazy
PostgreSQL (jej nazwa musi kończyć się na „test”, bo testy czyszczą tabele):
TEST_DATABASE_URL=postgresql+psycopg://user:pw@host/paneltest python -m unittest discover tests"""
import os, unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DATABASE_URL", os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://x:x@localhost/x"))
os.environ.setdefault("MAIN_HOST", "127.0.0.1")
os.environ.setdefault("AGENT_KEYS", "main,local")
for k in ("MAIN", "LOCAL"):
    os.environ.setdefault(f"AGENT_{k}_URL", "http://127.0.0.1:1"); os.environ.setdefault(f"AGENT_{k}_TOKEN", "t")
os.environ.setdefault("AGENT_LOCAL_NAME", "Dodatkowy")

from app import alerts, push
from app.alerts import step

T0 = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
def at(s): return T0 + timedelta(seconds=s)
def new(): return NS(active=False, announced=False, pending_since=None, since=None, last_notified=None)


class StepTests(unittest.TestCase):
    def test_fire_once_then_resolve(self):
        st = new()
        self.assertEqual(step(st, True, False, at(0), 0, 300), "fire")
        for i in range(1, 50):                                   # kolejne odczyty nie powtarzają powiadomienia
            self.assertIsNone(step(st, True, False, at(i * 15), 0, 300))
        self.assertEqual(step(st, False, True, at(800), 0, 300), "resolve")
        self.assertIsNone(step(st, False, True, at(815), 0, 300))

    def test_hold_time(self):
        st = new()
        self.assertIsNone(step(st, True, False, at(0), 180, 300))
        self.assertIsNone(step(st, True, False, at(120), 180, 300))
        self.assertIsNone(step(st, False, True, at(150), 180, 300))     # krótki skok: licznik się zeruje
        self.assertIsNone(step(st, True, False, at(160), 180, 300))
        self.assertIsNone(step(st, True, False, at(300), 180, 300))     # 140 s od nowego startu
        self.assertEqual(step(st, True, False, at(345), 180, 300), "fire")

    def test_hysteresis_band_keeps_alert(self):
        st = new(); step(st, True, False, at(0), 0, 300)
        self.assertIsNone(step(st, False, False, at(30), 0, 300))      # w paśmie histerezy: nadal aktywny
        self.assertTrue(st.active)
        self.assertEqual(step(st, False, True, at(60), 0, 300), "resolve")

    def test_cooldown_flapping_is_quiet_then_deferred_fire(self):
        st = new()
        self.assertEqual(step(st, True, False, at(0), 0, 300), "fire")
        self.assertEqual(step(st, False, True, at(30), 0, 300), "resolve")
        self.assertEqual(step(st, True, False, at(60), 0, 300), "quiet")        # za szybko po poprzednim
        self.assertIsNone(step(st, True, False, at(200), 0, 300))
        self.assertEqual(step(st, True, False, at(301), 0, 300), "fire")        # trwa po cooldownie: zgłoś
        self.assertEqual(step(st, False, True, at(400), 0, 300), "resolve")

    def test_quiet_resolve_has_no_notification(self):
        st = new(); step(st, True, False, at(0), 0, 300); step(st, False, True, at(10), 0, 300)
        self.assertEqual(step(st, True, False, at(20), 0, 300), "quiet")
        self.assertEqual(step(st, False, True, at(30), 0, 300), "quiet_resolve")


class EndpointTests(unittest.TestCase):
    def test_allowed(self):
        for u in ("https://fcm.googleapis.com/fcm/send/abc", "https://updates.push.services.mozilla.com/wpush/v2/x",
                  "https://web.push.apple.com/Q", "https://wns2-par02p.notify.windows.com/?token=1"):
            self.assertTrue(push.endpoint_allowed(u), u)

    def test_rejected(self):
        for u in ("http://fcm.googleapis.com/x", "https://evil.com/", "https://fcm.googleapis.com.evil.com/",
                  "https://127.0.0.1/", "https://192.168.1.10:8765/metrics", "https://a@fcm.googleapis.com/x",
                  "https://fcm.googleapis.com:8080/x", "https://evilpush.apple.com/x", "", "javascript:alert(1)"):
            self.assertFalse(push.endpoint_allowed(u), u)


TEST_DB = os.getenv("TEST_DATABASE_URL")
if TEST_DB and not TEST_DB.rsplit("/", 1)[-1].endswith("test"):
    raise SystemExit("TEST_DATABASE_URL musi wskazywać bazę o nazwie kończącej się na „test” (testy kasują tabele)")

@unittest.skipUnless(TEST_DB, "ustaw TEST_DATABASE_URL, aby uruchomić testy z bazą")
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import create_app
        from app.extensions import db
        cls.app = create_app(); cls.db = db
        cls.ctx = cls.app.app_context(); cls.ctx.push()
        db.drop_all(); db.create_all()

    @classmethod
    def tearDownClass(cls):
        cls.db.session.remove(); cls.db.drop_all(); cls.ctx.pop()

    def setUp(self):
        from app import models as m
        self.m = m
        for t in (m.AlertEvent, m.AlertState, m.AlertSettings, m.StatusEvent, m.AgentState, m.DockerState):
            t.query.delete()
        self.db.session.commit()
        self.sent = []
        self._orig = push.send
        push.send = lambda title, body, tag, url="/", urgent=False, user_id=None: (self.sent.append((title, tag, urgent)) or 1)

    def tearDown(self):
        push.send = self._orig

    def status(self, state, t):
        self.db.session.add(self.m.StatusEvent(state=state, ts=t)); self.db.session.commit()

    def agent(self, key, ok=True, cpu=10, ram=10, temp=40, disks=(("/", 10),), t=T0):
        d = {"cpu": {"percent": cpu}, "mem": {"percent": ram}, "temp_max": temp,
             "disks": [{"mount": m, "percent": p, "used": 5 * 1024**3, "total": 50 * 1024**3} for m, p in disks]}
        st = self.db.session.get(self.m.AgentState, key) or self.m.AgentState(server=key)
        st.ok, st.data, st.error, st.last_ok, st.checked = ok, d, None if ok else "Timeout", t, t
        self.db.session.add(st); self.db.session.commit()

    def containers(self, key, *cs):
        ds = self.db.session.get(self.m.DockerState, key) or self.m.DockerState(server=key)
        ds.ok, ds.data = True, {"containers": list(cs)}
        self.db.session.add(ds); self.db.session.commit()

    def test_main_down_once_and_recovery(self):
        self.status("ONLINE", at(0)); alerts.evaluate(at(1))
        self.assertEqual(self.sent, [])
        self.status("OFFLINE", at(10))
        for i in range(5): alerts.evaluate(at(20 + i * 15))
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self.sent[0][0].startswith("🔴") and self.sent[0][2])
        self.status("BOOTING", at(200)); alerts.evaluate(at(210))
        self.assertEqual(len(self.sent), 1)                       # start w toku to jeszcze nie „działa”
        self.status("ONLINE", at(260)); alerts.evaluate(at(270))
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(self.sent[1][0].startswith("✅"))
        self.assertEqual(self.sent[0][1], self.sent[1][1])        # ten sam tag: powiadomienie jest podmieniane

    def test_planned_shutdown_is_not_an_alert(self):
        self.status("ONLINE", at(0)); self.status("SHUTTING_DOWN", at(10)); self.status("OFFLINE", at(40))
        alerts.evaluate(at(50)); alerts.evaluate(at(65))
        self.assertEqual(self.sent, [])

    def test_failed_boot_is_an_alert(self):
        self.status("OFFLINE", at(0)); self.status("BOOTING", at(5)); self.status("OFFLINE", at(305))
        alerts.evaluate(at(310))
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Wake-on-LAN", self.db.session.query(self.m.AlertEvent).one().detail)

    def test_cpu_hold_hysteresis_and_resolve(self):
        self.status("ONLINE", at(0))
        cfg = alerts.get_settings(); cfg.update(cpu=90, hold_min=3); alerts.save_settings(cfg)
        self.agent("local", cpu=95); alerts.evaluate(at(0)); alerts.evaluate(at(120))
        self.assertEqual(self.sent, [])                           # jeszcze nie minęły 3 min
        alerts.evaluate(at(181)); self.assertEqual(len(self.sent), 1)
        self.agent("local", cpu=88); alerts.evaluate(at(200))     # poniżej progu, ale nie o 5 pkt
        self.assertEqual(len(self.sent), 1)
        self.agent("local", cpu=80); alerts.evaluate(at(215))
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(self.sent[1][0].startswith("✅"))

    def test_disabled_threshold_and_master_switch(self):
        self.status("ONLINE", at(0))
        cfg = alerts.get_settings(); cfg.update(ram=0, hold_min=1); alerts.save_settings(cfg)
        self.agent("local", ram=99); alerts.evaluate(at(0)); alerts.evaluate(at(120))
        self.assertEqual(self.sent, [])
        cfg.update(enabled=False); alerts.save_settings(cfg)
        self.agent("local", cpu=99); alerts.evaluate(at(0)); alerts.evaluate(at(500))
        self.assertEqual(self.sent, [])

    def test_container_crash_stop_and_removal(self):
        self.status("ONLINE", at(0))
        ok = dict(name="web", state="running", running=True, restarts=0, exit_code=0, oom=False, health=None)
        bad = dict(ok, state="exited", running=False, exit_code=1)
        stopped = dict(ok, state="exited", running=False, exit_code=0)
        self.containers("local", ok); alerts.evaluate(at(0)); self.assertEqual(self.sent, [])
        self.containers("local", bad); alerts.evaluate(at(30)); alerts.evaluate(at(45))
        self.assertEqual(len(self.sent), 1)
        self.assertIn("web", self.sent[0][0])
        self.containers("local", stopped); alerts.evaluate(at(60))          # zatrzymany celowo: cisza
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.m.AlertState.query.filter_by(active=True).count(), 0)
        self.containers("local", dict(bad, name="db")); alerts.evaluate(at(1000))   # po cooldownie nowy alert
        self.assertEqual(len(self.sent), 2)
        self.containers("local"); alerts.evaluate(at(1100))                 # kontener usunięty: cicho
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.m.AlertState.query.count(), 0)

    def test_main_agent_silent_when_main_off(self):
        self.status("ONLINE", at(0)); self.agent("main", cpu=99); alerts.evaluate(at(0))
        cfg = alerts.get_settings(); cfg.update(hold_min=1); alerts.save_settings(cfg)
        self.agent("main", ok=False); alerts.evaluate(at(0)); alerts.evaluate(at(100))   # main ONLINE, agent padł
        self.assertEqual(len(self.sent), 1)
        self.status("SHUTTING_DOWN", at(110)); self.status("OFFLINE", at(140))
        alerts.evaluate(at(150)); alerts.evaluate(at(400))
        self.assertEqual(len(self.sent), 1)                                  # bez dodatkowych alertów
        self.assertEqual(self.m.AlertState.query.filter_by(active=True).count(), 0)

    def test_unhealthy_container(self):
        self.status("ONLINE", at(0))
        c = dict(name="api", state="running", running=True, restarts=0, exit_code=0, oom=False, health="unhealthy")
        self.containers("local", c); alerts.evaluate(at(0))
        self.assertEqual(len(self.sent), 1); self.assertIn("niezdrowy", self.sent[0][0])
        self.containers("local", dict(c, health="healthy")); alerts.evaluate(at(30))
        self.assertEqual(len(self.sent), 2)


if __name__ == "__main__":
    unittest.main()
