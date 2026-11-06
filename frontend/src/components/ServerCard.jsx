import { get } from '../api.js';
import { usePoll } from '../hooks.js';
import { Bar, Pill, Time } from './ui.jsx';
import { gb, pct, rate, uptime } from '../format.js';

export default function ServerCard({ agent }) {
  const { data, error } = usePoll(() => get('/api/servers/' + agent.key), [agent.key], 10000);
  if (!data) return <section className="card">{error ? <p className="err">{error}</p> : '…'}</section>;
  const st = data.state, d = st && st.data;
  return (
    <section className="card">
      <div className="row"><h3 style={{ margin: 0 }}>{data.name}</h3>
        {!st ? <Pill cls="warn">brak danych</Pill> : st.ok ? <Pill cls="ok">agent OK</Pill> : <Pill cls="bad">agent nie odpowiada</Pill>}
      </div>
      {d && (
        <>
          {!st.ok && <p className="muted">Ostatnie znane dane z <Time iso={st.last_ok} /> ({st.error})</p>}
          <p className="muted">{d.hostname} · {d.os} · uptime {uptime(d.uptime)}<br />
            {d.cpu.model} · {d.cpu.cores} rdz. / {d.cpu.threads} wątków{d.cpu.freq_mhz ? ` · ${d.cpu.freq_mhz.toFixed(0)} MHz` : ''}</p>
          <div className="grid">
            <div><b>CPU</b> {pct(d.cpu.percent)}% <span className="muted">load {(d.cpu.load || []).map(x => +x.toFixed(2)).join(' / ')}</span><Bar p={d.cpu.percent} /></div>
            <div><b>RAM</b> {gb(d.mem.used)} / {gb(d.mem.total)} GB ({pct(d.mem.percent)}%)
              {d.mem.swap_total ? <span className="muted"> swap {gb(d.mem.swap_used)} / {gb(d.mem.swap_total)} GB</span> : null}<Bar p={d.mem.percent} /></div>
            {(d.disks || []).map(k => (
              <div key={k.mount}><b>{k.mount}</b> {gb(k.used)} / {gb(k.total)} GB ({pct(k.percent)}%) <span className="muted">{k.fstype}</span><Bar p={k.percent} /></div>
            ))}
            {(d.gpus || []).map((g, i) => (
              <div key={i}><b>GPU</b> {g.name} {pct(g.util)}% · VRAM {gb(g.mem_used)} / {gb(g.mem_total)} GB · {pct(g.temp)}°C<Bar p={g.util} /></div>
            ))}
            {d.temp_max != null && (
              <div><b>Temp.</b> {pct(d.temp_max)}°C <span className="muted">{(d.temps || []).slice(0, 4).map(t => `${t.label} ${pct(t.current)}° `).join('')}</span></div>
            )}
            <div><b>Sieć</b> ↓ {rate((d.rates || {}).rx)} · ↑ {rate((d.rates || {}).tx)}</div>
          </div>
        </>
      )}
    </section>
  );
}
