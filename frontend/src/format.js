const p = n => String(n).padStart(2, '0');

// Czas w strefie przeglądarki użytkownika: dd.mm HH:MM:SS
export function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return '—';
  return `${p(d.getDate())}.${p(d.getMonth() + 1)} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export const fmtShort = t => new Date(t).toLocaleString('pl', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

export const gb = v => ((v || 0) / 1024 ** 3).toFixed(1);
export const mb = v => `${((v || 0) / 1024 ** 2).toFixed(0)} MB`;
export const pct = v => Number(v || 0).toFixed(0);

export function rate(v) {
  v = v || 0;
  for (const u of ['B/s', 'KB/s', 'MB/s', 'GB/s']) {
    if (v < 1024) return u === 'B/s' ? `${v.toFixed(0)} ${u}` : `${v.toFixed(1)} ${u}`;
    v /= 1024;
  }
  return `${v.toFixed(1)} TB/s`;
}

export function uptime(sec) {
  sec = Math.max(0, Math.floor(sec || 0));
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  return d ? `${d}d ${h}h ${m}m` : `${h}h ${m}m`;
}

export const RANGES_PING = ['1h', '6h', '24h', '7d', '30d'];
export const tickFmt = range => range.endsWith('d')
  ? { day: '2-digit', month: '2-digit', hour: '2-digit' }
  : { hour: '2-digit', minute: '2-digit' };
