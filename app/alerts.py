"""Silnik alertów: zamienia dane z workera (status serwera, metryki, kontenery) na powiadomienia push.

Każdy alert ma stan w tabeli `alert_state`. Powiadomienie idzie tylko przy zmianie stanu
(wystąpił / ustąpił), a nie przy każdym odczycie, dlatego ten sam alert nie przychodzi wielokrotnie:
- histereza: alert z progiem ustępuje dopiero po spadku o HYST poniżej progu,
- czas trzymania: CPU, RAM, dysk, temperatura i agent muszą być w złym stanie `hold_min` minut,
- cooldown: ponowne wystąpienie tego samego alertu w ciągu ALERT_COOLDOWN s po poprzednim powiadomieniu
  jest wstrzymane (pętla restartów kontenera nie zasypie telefonu), a jeśli problem trwa dalej, zostaje zgłoszony po cooldownie.
"""
import logging, os
from zoneinfo import ZoneInfo
from flask import current_app
from . import agents, push
from .dockerstate import state_of, _crash_detail
from .extensions import db
from .models import (AgentState, AlertEvent, AlertSettings, AlertState, DockerState,
                     StatusEvent, now)

log = logging.getLogger("alerts")

HYST = 5.0                                              # punkty % lub °C poniżej progu, by alert ustąpił
COOLDOWN = int(os.getenv("ALERT_COOLDOWN", 300))        # s
MAIN_KEY = os.getenv("MAIN_AGENT_KEY", "main")          # klucz agenta działającego na serwerze głównym
TZ = ZoneInfo(os.getenv("PANEL_TZ", "Europe/Warsaw"))

DEFAULTS = {"enabled": True, "main_down": True, "agent_down": True, "containers": True, "resolved": True,
            "cpu": 90, "ram": 90, "disk": 90, "temp": 80, "hold_min": 3}   # progi: 0 = wyłączony
LIMITS = {"cpu": (0, 100), "ram": (0, 100), "disk": (0, 100), "temp": (0, 150), "hold_min": (1, 60)}
FLAGS = ("enabled", "main_down", "agent_down", "containers", "resolved")


def get_settings():
    row = db.session.get(AlertSettings, 1)
    cfg = dict(DEFAULTS)
    for k, v in ((row.data if row else None) or {}).items():
        if k in DEFAULTS and isinstance(v, type(DEFAULTS[k])):
            cfg[k] = v
    return cfg


def save_settings(cfg):
    row = db.session.get(AlertSettings, 1) or AlertSettings(id=1, data={})
    row.data = {k: cfg[k] for k in DEFAULTS if k in cfg}
    db.session.add(row)
    db.session.commit()


def step(st, breached, clear, t, hold_s, cooldown_s):
    """Maszyna stanów jednego alertu. `st` ma pola active, announced, pending_since, since, last_notified
    (jest modyfikowany). `breached`: warunek alertu spełniony; `clear`: warunek całkiem ustąpił
    (dla progów: wartość poniżej progu minus histereza). Pomiędzy nimi stan się nie zmienia.
    Zwraca: 'fire' (alert + powiadomienie), 'quiet' (alert bez powiadomienia, cooldown),
    'resolve' (ustąpił, były powiadomienie), 'quiet_resolve' (ustąpił po cichym alercie) albo None."""
    if not st.active:
        if not breached:
            st.pending_since = None
            return None
        if hold_s > 0:
            if st.pending_since is None:
                st.pending_since = t
            if (t - st.pending_since).total_seconds() < hold_s:
                return None
        st.active, st.since, st.pending_since = True, t, None
        if st.last_notified is None or (t - st.last_notified).total_seconds() >= cooldown_s:
            st.announced, st.last_notified = True, t
            return "fire"
        st.announced = False
        return "quiet"
    if clear:
        was = st.announced
        st.active = st.announced = False
        st.pending_since = None
        return "resolve" if was else "quiet_resolve"
    if not st.announced and (t - st.last_notified).total_seconds() >= cooldown_s:
        st.announced, st.last_notified = True, t     # problem trwa po cooldownie: zgłaszamy z opóźnieniem
        return "fire"
    return None


class Engine:
    def __init__(self, cfg, t):
        self.cfg, self.t, self.out = cfg, t, []
        self.states = {s.key: s for s in AlertState.query.all()}

    def observe(self, key, breached, clear, fire, resolved, hold_s=0, url="/"):
        """fire / resolved: (tytuł, treść) powiadomienia o wystąpieniu i o ustąpieniu."""
        st = self.states.get(key)
        if st is None:
            if not breached:
                return
            st = self.states[key] = AlertState(key=key, active=False, announced=False)
            db.session.add(st)
        r = step(st, breached, clear, self.t, hold_s, COOLDOWN)
        if st.active:
            st.title, st.detail = fire[0][:160], fire[1][:300]
        if r:
            self.out.append((r, key, resolved if r in ("resolve", "quiet_resolve") else fire, url))

    def reset(self, key):
        """Cicho kasuje alert (bez powiadomienia): np. celowe zatrzymanie, wyłączony próg, brak danych z wyłączonego serwera."""
        st = self.states.get(key)
        if st is not None:
            st.active = st.announced = False
            st.pending_since = None

    def reset_prefix(self, *prefixes):
        for k in list(self.states):
            if k.startswith(prefixes):
                self.reset(k)

    def drop_missing(self, prefix, present):
        """Alerty elementów, które zniknęły (usunięty kontener, odmontowany dysk), kończymy cicho."""
        for k, st in list(self.states.items()):
            if k.startswith(prefix) and k[len(prefix):] not in present:
                if st.active:
                    self.out.append(("gone", k, (st.title or k, "element zniknął"), "/"))
                db.session.delete(st)
                del self.states[k]

    def flush(self):
        for r, key, (title, detail), url in self.out:
            pushed = 0
            if r == "fire" or (r == "resolve" and self.cfg["resolved"]):
                pushed = push.send(("🔴 " if r == "fire" else "✅ ") + title, detail, tag=key, url=url, urgent=(r == "fire"))
            quiet = r in ("quiet", "quiet_resolve", "gone")
            db.session.add(AlertEvent(key=key, kind="fire" if r in ("fire", "quiet") else "resolve",
                                      title=title[:160], detail=(detail + (" (bez powiadomienia)" if quiet else ""))[:300],
                                      pushed=pushed))
        db.session.commit()


def _hm(dt):
    return dt.astimezone(TZ).strftime("%H:%M") if dt else "?"


def _main_state():
    evs = StatusEvent.query.order_by(StatusEvent.id.desc()).limit(2).all()
    return (evs[0] if evs else None), (evs[1] if len(evs) > 1 else None)


def _check_main(eng):
    last, prev = _main_state()
    if not eng.cfg["main_down"]:
        eng.reset("main_down"); return
    if last is None:
        return
    name = current_app.config["MAIN_NAME"]
    # OFFLINE po SHUTTING_DOWN to celowe wyłączenie z panelu, nie awaria
    planned = last.state == "OFFLINE" and prev is not None and prev.state == "SHUTTING_DOWN"
    down = last.state == "OFFLINE" and not planned
    why = " (nie wstał po Wake-on-LAN)" if prev is not None and prev.state == "BOOTING" else ""
    eng.observe("main_down", down, last.state == "ONLINE" or planned,
                (f"{name} nie odpowiada", f"Brak odpowiedzi od {_hm(last.ts)}{why}"),
                (f"{name} działa", "Odpowiada ponownie"))


def _check_agents(eng, main_online):
    cfg = eng.cfg
    for a in agents.AGENTS.values():
        k, name = a["key"], a["name"]
        if k == MAIN_KEY and not main_online:            # serwer główny wyłączony: brak agenta jest oczywisty
            eng.reset_prefix(f"agent:{k}", f"cpu:{k}", f"ram:{k}", f"temp:{k}", f"disk:{k}:", f"ctr:{k}:")
            continue
        st = db.session.get(AgentState, k)
        if st is None:
            continue
        hold = cfg["hold_min"] * 60
        if cfg["agent_down"]:
            eng.observe(f"agent:{k}", not st.ok, bool(st.ok),
                        (f"Agent „{name}” nie odpowiada", f"Brak danych od {_hm(st.last_ok)} ({st.error or 'błąd'})"),
                        (f"Agent „{name}” odpowiada", "Dane znów są odbierane"), hold_s=hold)
        else:
            eng.reset(f"agent:{k}")
        if not (st.ok and st.data):
            continue                                     # bez świeżych danych nie rozstrzygamy progów
        d = st.data
        def thr(key, value, limit, fire, resolved):
            if not limit or value is None:
                eng.reset(key); return
            eng.observe(key, value >= limit, value < limit - HYST, fire, resolved, hold_s=hold)
        v = d["cpu"]["percent"]
        thr(f"cpu:{k}", v, cfg["cpu"], (f"Wysokie CPU: {name}", f"{v:.0f}% (próg {cfg['cpu']}%)"),
            (f"CPU w normie: {name}", f"{v:.0f}%"))
        v = d["mem"]["percent"]
        thr(f"ram:{k}", v, cfg["ram"], (f"Wysokie użycie RAM: {name}", f"{v:.0f}% (próg {cfg['ram']}%)"),
            (f"RAM w normie: {name}", f"{v:.0f}%"))
        v = d.get("temp_max")
        thr(f"temp:{k}", v, cfg["temp"], (f"Wysoka temperatura: {name}", f"{v or 0:.0f}°C (próg {cfg['temp']}°C)"),
            (f"Temperatura w normie: {name}", f"{v or 0:.0f}°C"))
        mounts = set()
        for disk in d.get("disks", []):
            m, v = disk["mount"], disk["percent"]
            mounts.add(m)
            gb = lambda x: f"{x / 1024**3:.0f}"
            thr(f"disk:{k}:{m}", v, cfg["disk"],
                (f"Mało miejsca na dysku: {name} {m}", f"{v:.0f}% zajęte ({gb(disk['used'])} z {gb(disk['total'])} GB)"),
                (f"Dysk w normie: {name} {m}", f"{v:.0f}% zajęte"))
        eng.drop_missing(f"disk:{k}:", mounts)


def _check_containers(eng, main_online):
    for a in agents.AGENTS.values():
        k, name = a["key"], a["name"]
        if not eng.cfg["containers"]:
            eng.reset_prefix(f"ctr:{k}:"); continue
        if k == MAIN_KEY and not main_online:
            continue                                     # reset zrobił już _check_agents
        ds = db.session.get(DockerState, k)
        if ds is None or not ds.ok or not ds.data:
            continue                                     # brak świeżych danych: nie zmieniamy stanu
        names = set()
        for c in ds.data.get("containers", []):
            n = c["name"]; names.add(n)
            key, s = f"ctr:{k}:{n}", state_of(c)
            sick = s == "up" and c.get("health") == "unhealthy"
            if s == "stopped":                           # zatrzymany celowo (kod 0/137/143) lub wstrzymany
                eng.reset(key); continue
            if sick:
                fire = (f"Kontener {n} niezdrowy ({name})", "Nie przechodzi health-checka")
            elif c["state"] == "restarting":
                fire = (f"Kontener {n} padł ({name})", f"W pętli restartów ({c.get('restarts', 0)}×)")
            else:
                fire = (f"Kontener {n} padł ({name})", _crash_detail(c).capitalize())
            eng.observe(key, s == "crashed" or sick, s == "up" and not sick, fire,
                        (f"Kontener {n} działa ({name})", "Wrócił do normy"), url="/docker")
        eng.drop_missing(f"ctr:{k}:", names)


def evaluate(t=None):
    """Jedno przejście po wszystkich warunkach. Wywoływane z workera; wymaga app context.
    `t` (tylko w testach) podmienia aktualny czas."""
    cfg = get_settings()
    if not cfg["enabled"]:
        return []
    eng = Engine(cfg, t or now())
    last, _ = _main_state()
    main_online = bool(last and last.state == "ONLINE")
    _check_main(eng)
    _check_agents(eng, main_online)
    _check_containers(eng, main_online)
    db.session.commit()                                  # stan zapisujemy przed wysyłką: awaria pushu nie powtórzy alertu
    eng.flush()
    return eng.out


def active_alerts():
    return AlertState.query.filter_by(active=True).order_by(AlertState.since).all()


def recent_events(n=20):
    return AlertEvent.query.order_by(AlertEvent.id.desc()).limit(n).all()
