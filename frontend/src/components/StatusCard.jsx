import { useState } from 'react';
import { action, get } from '../api.js';
import { usePoll } from '../hooks.js';
import { Msg, Pill, Time } from './ui.jsx';

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
      <div>
        {!s ? (error ? <p className="err">{error}</p> : '…') : s.stale ? (
          <><Pill cls="warn">BRAK DANYCH</Pill><p className="muted">Worker nie zapisuje pomiarów.</p></>
        ) : (
          <>
            <Pill cls={CLS[s.state] || 'warn'}>{LABEL[s.state] || '—'}</Pill>
            <p>{s.host} &middot; ICMP: {s.icmp_ok ? `${s.icmp_ms.toFixed(1)} ms` : 'brak'}
              {' '}&middot; TCP: {s.tcp_ok ? `${s.tcp_ms.toFixed(1)} ms` : 'brak'}</p>
            {s.since && <p className="muted">od <Time iso={s.since} /></p>}
          </>
        )}
      </div>
      <div className="row">
        <button onClick={wake} disabled={busy}>Włącz (WoL)</button>
        <form className="row" onSubmit={shutdown}>
          <input type="password" placeholder="Hasło" autoComplete="current-password" required
                 style={{ width: '11rem' }} value={pw} onChange={e => setPw(e.target.value)} />
          <button className="danger" disabled={busy}>Wyłącz</button>
        </form>
      </div>
      <Msg msg={msg} />
    </section>
  );
}
