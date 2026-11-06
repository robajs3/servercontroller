import { useCallback, useEffect, useState } from 'react';
import { ApiError, get, post } from '../api.js';
import { usePoll } from '../hooks.js';
import { Loading, Msg, Pill, Time } from '../components/ui.jsx';
import { disablePush, enablePush, getSub, hasPush, isIOS, standalone, testPush } from '../pwa.js';

export default function Notifications() {
  const { data, error, reload } = usePoll(() => get('/api/notifications'), [], 0);
  if (!data) return <Loading error={error} />;
  return (
    <>
      <PushCard configured={data.configured} />
      <Active items={data.active} />
      <SettingsForm settings={data.settings} limits={data.limits} />
      <Devices subs={data.subs} onChanged={reload} />
      <History events={data.events} />
    </>
  );
}

// ---- „To urządzenie” ----
function PushCard({ configured }) {
  const [status, setStatus] = useState('Sprawdzam…');
  const [err, setErr] = useState(null);
  const [btn, setBtn] = useState({ on: false, off: false });

  const render = useCallback(async () => {
    setErr(null);
    const show = (text, o = {}) => { setStatus(text); setBtn({ on: !!o.on, off: !!o.off }); };
    if (!hasPush) {
      show(isIOS && !standalone()
        ? 'Na iPhonie i iPadzie powiadomienia działają tylko w zainstalowanej aplikacji: Udostępnij → Do ekranu początkowego, a potem otwórz panel z ikony (iOS 16.4+).'
        : 'Ta przeglądarka nie obsługuje powiadomień push.');
      return;
    }
    if (Notification.permission === 'denied') { show('Powiadomienia są zablokowane w ustawieniach przeglądarki dla tej strony. Odblokuj je i odśwież stronę.'); return; }
    const sub = await getSub().catch(() => null);
    if (sub && Notification.permission === 'granted') show('Powiadomienia są włączone na tym urządzeniu.', { off: true });
    else show('Powiadomienia są wyłączone na tym urządzeniu.', { on: true });
  }, []);
  useEffect(() => { render(); }, [render]);

  const run = fn => async () => { try { await fn(); } catch (e) { setErr(e.message || String(e)); } await render(); };
  return (
    <section className="card">
      <h3>To urządzenie</h3>
      {!configured && <p className="err">Serwer nie ma skonfigurowanych kluczy VAPID: wygeneruj je komendą{' '}
        <code>docker compose exec web flask --app app gen-vapid</code>, wklej do <code>.env</code> i uruchom ponownie (<code>docker compose up -d</code>).</p>}
      <p className="muted">{status}</p>
      {err && <p className="err">{err}</p>}
      <div className="row">
        {btn.on && <button onClick={run(enablePush)}>Włącz powiadomienia</button>}
        {btn.off && <button className="ghost" onClick={run(testPush)}>Wyślij testowe</button>}
        {btn.off && <button className="ghost" onClick={run(disablePush)}>Wyłącz na tym urządzeniu</button>}
      </div>
    </section>
  );
}

function Active({ items }) {
  return (
    <section className="card">
      <h3>Aktywne alerty</h3>
      {items.length ? (
        <table><thead><tr><th>Od</th><th>Alert</th><th></th></tr></thead><tbody>
          {items.map((a, i) => <tr key={i}><td><Time iso={a.since} /></td><td>{a.title}</td><td className="muted">{a.detail}</td></tr>)}
        </tbody></table>
      ) : <p className="ok-t">Brak aktywnych alertów.</p>}
    </section>
  );
}

// ---- „Alerty i progi” ----
const FLAGS = [
  ['enabled', 'Wysyłaj powiadomienia (przełącznik główny)'],
  ['main_down', 'Serwer główny przestał odpowiadać', '(wyłączenie przyciskiem w panelu nie jest alertem)'],
  ['agent_down', 'Agent na serwerze nie odpowiada'],
  ['containers', 'Kontener padł, restartuje się w pętli lub jest niezdrowy', '(zatrzymanie celowe nie jest alertem)'],
  ['resolved', 'Powiadom też, gdy problem ustąpi'],
];
const NUMS = [['cpu', 'CPU od (%)'], ['ram', 'RAM od (%)'], ['disk', 'Dysk od (%)'], ['temp', 'Temperatura od (°C)'], ['hold_min', 'Utrzymuje się przez (min)']];

function SettingsForm({ settings, limits }) {
  const [f, setF] = useState(settings);
  const [msg, setMsg] = useState(null);
  const submit = async e => {
    e.preventDefault();
    const body = { ...f };
    for (const [k] of NUMS) body[k] = f[k] === '' ? null : Number(f[k]);
    try {
      const j = await post('/api/notifications/settings', body);
      setF(j.settings); setMsg({ ok: true, message: j.message });
    } catch (x) { setMsg({ ok: false, message: x instanceof ApiError ? x.message : String(x) }); }
  };
  return (
    <form className="card" onSubmit={submit}>
      <h3>Alerty i progi</h3>
      {FLAGS.map(([k, label, hint]) => (
        <p key={k}><label><input type="checkbox" checked={!!f[k]} style={{ width: 'auto' }}
                                 onChange={e => setF({ ...f, [k]: e.target.checked })} /> {label}{hint && <> <span className="muted">{hint}</span></>}</label></p>
      ))}
      <div className="grid">
        {NUMS.map(([k, label]) => (
          <label key={k}>{label} <input type="number" min={limits[k][0]} max={limits[k][1]} value={f[k]}
                                         onChange={e => setF({ ...f, [k]: e.target.value })} /></label>
        ))}
      </div>
      <p className="muted">0 wyłącza dany próg. Alert pojawia się, gdy wartość utrzymuje się powyżej progu przez podany czas, a ustępuje dopiero po spadku o 5 poniżej progu.</p>
      <button>Zapisz</button>
      <Msg msg={msg} />
    </form>
  );
}

function Devices({ subs, onChanged }) {
  const [err, setErr] = useState(null);
  const del = async s => {
    if (!window.confirm('Usunąć to urządzenie z powiadomień?')) return;
    try { await post('/api/push/delete', { id: s.id }); onChanged(); } catch (e) { setErr(e.message); }
  };
  return (
    <section className="card">
      <h3>Urządzenia z powiadomieniami</h3>
      {err && <p className="err">{err}</p>}
      {subs.length ? (
        <table><thead><tr><th>Urządzenie</th><th>Dodano</th><th>Ostatnia dostawa</th><th></th></tr></thead><tbody>
          {subs.map(s => (
            <tr key={s.id}><td>{s.device}</td><td><Time iso={s.created} /></td><td><Time iso={s.last_ok} /></td>
              <td><button className="ghost sm" onClick={() => del(s)}>Usuń</button></td></tr>
          ))}
        </tbody></table>
      ) : <p className="muted">Żadne urządzenie nie ma jeszcze włączonych powiadomień.</p>}
    </section>
  );
}

function History({ events }) {
  return (
    <section className="card">
      <h3>Historia alertów</h3>
      {events.length ? (
        <div className="scroll"><table><thead><tr><th>Czas</th><th></th><th>Alert</th><th>Szczegóły</th></tr></thead><tbody>
          {events.map((e, i) => (
            <tr key={i}><td><Time iso={e.ts} /></td>
              <td><Pill sm cls={e.kind === 'fire' ? 'bad' : 'ok'}>{e.kind === 'fire' ? 'wystąpił' : 'ustąpił'}</Pill></td>
              <td>{e.title}</td><td className="muted">{e.detail}</td></tr>
          ))}
        </tbody></table></div>
      ) : <p className="muted">Brak zdarzeń.</p>}
    </section>
  );
}
