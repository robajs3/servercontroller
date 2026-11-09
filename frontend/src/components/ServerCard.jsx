import { get } from '../api.js';
import { usePoll } from '../hooks.js';
import { Bar, Pill, Time, Tile, Updated } from './ui.jsx';
import { gb, pct, rate, uptime } from '../format.js';

export default function ServerCard({ agent }) {
  const { data, error, updatedAt } = usePoll(() => get('/api/servers/' + agent.key), [agent.key], 10000);
  if (!data) return <section className="card">{error ? <p className="err">{error}</p> : '…'}</section>;
  const st = data.state, d = st && st.data;
  return (
    <section className="card">
      <div className="row"><h3>{data.name}</h3>
        {!st ? <Pill cls="warn">brak danych</Pill> : st.ok ? <Pill cls="ok">agent OK</Pill> : <Pill cls="bad">agent nie odpowiada</Pill>}
      </div>
      <Updated at={updatedAt} error={error} />
      {d && (
        <>
          {!st.ok && <p className="muted">Ostatnie znane dane z <Time iso={st.last_ok} /> ({st.error})</p>}
          <p className="muted sysinfo">{d.hostname} · {d.os} · uptime {uptime(d.uptime)}<br />
            {d.cpu.model} · {d.cpu.cores} rdz. / {d.cpu.threads} wątków{d.cpu.freq_mhz ? ` · ${d.cpu.freq_mhz.toFixed(0)} MHz` : ''}</p>
          <div className="metrics">
            <Tile label="CPU" value={`${pct(d.cpu.percent)}%`} p={d.cpu.percent}
                  sub={`load ${(d.cpu.load || []).map(x => +x.toFixed(2)).join(' / ')}`} />
            <Tile label="RAM" value={`${pct(d.mem.percent)}%`} p={d.mem.percent}
                  sub={`${gb(d.mem.used)} / ${gb(d.mem.total)} GB${d.mem.swap_total ? ` · swap ${gb(d.mem.swap_used)} / ${gb(d.mem.swap_total)} GB` : ''}`} />
            {(d.disks || []).map(k => (
              <Tile key={k.mount} label={k.mount} value={`${pct(k.percent)}%`} p={k.percent}
                    sub={`${gb(k.used)} / ${gb(k.total)} GB · ${k.fstype}`} />
            ))}
            {(d.gpus || []).map((g, i) => (
              <Tile key={i} wide label="GPU" value={`${pct(g.util)}%`} p={g.util}
                    sub={`${g.name} · VRAM ${gb(g.mem_used)} / ${gb(g.mem_total)} GB · ${pct(g.temp)}°C`} />
            ))}
            {d.temp_max != null && (
              <Tile label="Temp." value={`${pct(d.temp_max)}°C`}
                    sub={(d.temps || []).slice(0, 4).map(t => `${t.label} ${pct(t.current)}°`).join(' ')} />
            )}
            <Tile label="Sieć">
              <b className="t-val net">↓ {rate((d.rates || {}).rx)}</b>
              <b className="t-val net">↑ {rate((d.rates || {}).tx)}</b>
            </Tile>
          </div>
        </>
      )}
    </section>
  );
}