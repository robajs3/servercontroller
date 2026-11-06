import { useState } from 'react';
import { action, get } from '../api.js';
import { usePoll } from '../hooks.js';
import { Msg, Pill, Time, Tile } from './ui.jsx';

const LABEL = { ONLINE: 'ONLINE', OFFLINE: 'OFFLINE', BOOTING: 'URUCHAMIANIE…', SHUTTING_DOWN: 'WYŁĄCZANIE…' };
const CLS = { ONLINE: 'ok', OFFLINE: 'bad' };

export default function StatusCard({ name }) {
  const { data: s, error, reload } = usePoll(() => get('/api/status'), [], 5000);
  const [pw, setPw] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async (url, body) => {
    setBusy(true);
    setMsg(await action(url, body));
    setBusy(false);
    reload();
  };
  const wake = () => window.confirm('Wysłać Wake-on-LAN?') && run('/api/actions/wake');
  const shutdown = e => {
    e.preventDefault();
    if (!window.confirm('Na pewno wyłączyć serwer?')) return;
    run('/api/actions/shutdown', { password: pw }).then(() => setPw(''));
  };

  return (
    <section className="card">
      <h3>{name}</h3>
      {!s ? (error ? <p className="err">{error}</p> : '…') : s.stale ? (
        <><Pill cls="warn">BRAK DANYCH</Pill><p className="muted">Worker nie zapisuje pomiarów.</p></>
      ) : (
        <div className="metrics">
          <Tile wide label="Status" sub={s.host}>
            <span><Pill cls={CLS[s.state] || 'warn'}>{LABEL[s.state] || '—'}</Pill></span>
          </Tile>
          <Tile label="ICMP" value={s.icmp_ok ? `${s.icmp_ms.toFixed(1)} ms` : 'brak'} />
          <Tile label="TCP" value={s.tcp_ok ? `${s.tcp_ms.toFixed(1)} ms` : 'brak'} />
          {s.since && <Tile wide label="Od"><b className="t-val net"><Time iso={s.since} /></b></Tile>}
        </div>
      )}
      <div className="ctrl">
        <button onClick={wake} disabled={busy}>Włącz (WoL)</button>
        <form onSubmit={shutdown}>
          <input type="password" placeholder="Hasło" autoComplete="current-password" required
                 value={pw} onChange={e => setPw(e.target.value)} />
          <button className="danger" disabled={busy}>Wyłącz</button>
        </form>
      </div>
      <Msg msg={msg} />
    </section>
  );
}
