import { useMemo, useState } from 'react';
import { get, qs } from '../api.js';
import { usePoll } from '../hooks.js';
import { RANGES_PING } from '../format.js';
import ChartCanvas from './ChartCanvas.jsx';
import { RangeButtons, Updated } from './ui.jsx';

const SCALES = { y: { beginAtZero: true, suggestedMax: 100 } };
const line = (label, data, c) => ({ label, data, borderColor: c, pointRadius: 0, tension: .2 });

export default function ResourcesChart({ agents }) {
  const [srv, setSrv] = useState(agents[0].key);
  const [range, setRange] = useState('1h');
  const { data, error, updatedAt } = usePoll(() => get('/api/metrics?' + qs({ server: srv, range })), [srv, range], 15000);
  const { labels, datasets } = useMemo(() => {
    const d = data || [];
    return {
      labels: d.map(x => x.t),
      datasets: [line('CPU %', d.map(x => x.cpu), '#60a5fa'), line('RAM %', d.map(x => x.ram), '#c084fc'), line('Temp °C', d.map(x => x.temp), '#fb923c')],
    };
  }, [data]);
  return (
    <section className="card">
      <div className="row"><h3>Zasoby</h3>
        {agents.map(a => <button key={a.key} className="ghost" aria-pressed={a.key === srv} onClick={() => setSrv(a.key)}>{a.name}</button>)}
        <RangeButtons ranges={RANGES_PING} value={range} onChange={setRange} />
      </div>
      <Updated at={updatedAt} error={error} />
      {error && <p className="err">Nie udało się pobrać danych: {error}</p>}
      <ChartCanvas labels={labels} datasets={datasets} range={range} scales={SCALES} />
    </section>
  );
}