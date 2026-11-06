import { useMemo, useState } from 'react';
import { get, qs } from '../api.js';
import { usePoll } from '../hooks.js';
import { RANGES_PING } from '../format.js';
import ChartCanvas from './ChartCanvas.jsx';
import { RangeButtons } from './ui.jsx';

const SCALES = {
  y: { beginAtZero: true, title: { display: true, text: 'ms' } },
  y1: { position: 'right', min: 0, max: 100, grid: { drawOnChartArea: false } },
};

export default function PingChart() {
  const [range, setRange] = useState('1h');
  const { data, error } = usePoll(() => get('/api/ping?' + qs({ range })), [range], 15000);
  const { labels, datasets } = useMemo(() => {
    const d = data || [];
    return {
      labels: d.map(x => x.t),
      datasets: [
        { label: 'ping śr. (ms)', data: d.map(x => x.rtt), borderColor: '#4ade80', pointRadius: 0, tension: .2, yAxisID: 'y', spanGaps: false },
        { label: 'max (ms)', data: d.map(x => x.max), borderColor: '#60a5fa55', pointRadius: 0, yAxisID: 'y' },
        { label: 'utrata (%)', type: 'bar', data: d.map(x => x.loss), backgroundColor: '#f87171', yAxisID: 'y1' },
      ],
    };
  }, [data]);
  return (
    <section className="card">
      <div className="row"><h3>Ping</h3><RangeButtons ranges={RANGES_PING} value={range} onChange={setRange} /></div>
      {error && <p className="err">Nie udało się pobrać danych: {error}</p>}
      <ChartCanvas labels={labels} datasets={datasets} range={range} scales={SCALES} />
    </section>
  );
}
