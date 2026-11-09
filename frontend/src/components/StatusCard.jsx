import { useState } from 'react';
import { action, get } from '../api.js';
import { usePoll } from '../hooks.js';
import { Msg, Pill, Time, Tile, Updated } from './ui.jsx';
import ConfirmDialog from './ConfirmDialog.jsx';

const LABEL = { ONLINE: 'ONLINE', OFFLINE: 'OFFLINE', BOOTING: 'URUCHAMIANIE…', SHUTTING_DOWN: 'WYŁĄCZANIE…' };
const CLS = { ONLINE: 'ok', OFFLINE: 'bad' };

export default function StatusCard({ name }) {
  const { data: s, error, updatedAt, reload } = usePoll(() => get('/api/status'), [], 5000);
  const [pw, setPw] = useState('');
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dlg, setDlg] = useState(null);   // null | 'wake' | 'shutdown'

  const close = () => { setDlg(null); setPw(''); };

  const run = async (url, body) => {
    setBusy(true);
    setMsg(await action(url, body));
    setBusy(false);
    close();
    reload();
  };

  // Przyciski zależne od stanu serwera; przy braku danych (stale) stanu nie znamy
  const state = s && !s.stale ? s.state : null;
  const canWake = !busy && state !== 'ONLINE' && state !== 'BOOTING';
  const canShutdown = !busy && state === 'ONLINE';

  return (
    <section className="card">
      <h3>{name}</h3>
      <Updated at={updatedAt} error={error} />
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
        <button onClick={() => setDlg('wake')} disabled={!canWake}>Włącz (WoL)</button>
        <button className="danger" onClick={() => setDlg('shutdown')} disabled={!canShutdown}>Wyłącz</button>
      </div>
      <Msg msg={msg} />

      <ConfirmDialog open={dlg === 'wake'} title={`Włączyć ${name}?`} confirmLabel="Wyślij WoL"
                     busy={busy} onConfirm={() => run('/api/actions/wake')} onCancel={close}>
        <p>Do serwera {name} zostanie wysłany pakiet Wake-on-LAN.</p>
      </ConfirmDialog>

      <ConfirmDialog open={dlg === 'shutdown'} title={`Wyłączyć ${name}?`} confirmLabel="Wyłącz" danger
                     busy={busy} onConfirm={() => run('/api/actions/shutdown', { password: pw })} onCancel={close}>
        <label>Hasło do konta
          <input type="password" autoComplete="current-password" required
                 value={pw} onChange={e => setPw(e.target.value)} />
        </label>
      </ConfirmDialog>
    </section>
  );
}