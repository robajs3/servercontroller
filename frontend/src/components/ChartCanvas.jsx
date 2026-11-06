import { useEffect, useRef } from 'react';
import {
  BarController, BarElement, CategoryScale, Chart, Legend, LineController, LineElement,
  LinearScale, PointElement, Tooltip,
} from 'chart.js';
import { tickFmt } from '../format.js';

Chart.register(BarController, BarElement, CategoryScale, Legend, LineController, LineElement, LinearScale, PointElement, Tooltip);
Chart.defaults.color = '#8b93a1';
Chart.defaults.borderColor = '#262a33';

// Wykres liniowy z osią czasu (etykiety = ISO). `range` wpływa tylko na format etykiet osi X.
// Instancja powstaje raz; dane podmieniane są bez animacji, jak w oryginale.
export default function ChartCanvas({ labels, datasets, range, scales = {} }) {
  const ref = useRef(null);
  const chart = useRef(null);
  const rangeRef = useRef(range);
  rangeRef.current = range;

  useEffect(() => {
    chart.current = new Chart(ref.current, {
      type: 'line',
      data: { labels: [], datasets: [] },
      options: {
        animation: false, interaction: { mode: 'index', intersect: false },
        scales: {
          x: { type: 'category', ticks: { maxTicksLimit: 8, callback(v) {
            return new Date(this.getLabelForValue(v)).toLocaleString('pl', tickFmt(rangeRef.current));
          } } },
          ...scales,
        },
      },
    });
    return () => { chart.current.destroy(); chart.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const c = chart.current; if (!c) return;
    c.data.labels = labels;
    c.data.datasets = datasets;
    c.update('none');
  }, [labels, datasets, range]);

  return <canvas ref={ref} height="110" />;
}
