// Mocki API: praca nad frontem bez backendu. Włączane przez VITE_USE_MOCKS=1 (npm run dev:mock).
// W konsoli przeglądarki: __mock.fail = true (błąd sieci), __mock.stale = true (brak pomiarów).
import { ApiError } from '../api.js';

const ctl = (globalThis.__mock = { fail: false, stale: false });
const delay = ms => new Promise(r => setTimeout(r, ms));
const rnd = (a, b) => a + Math.random() * (b - a);
const GB = 1024 ** 3;

let state = 'ONLINE';                        // ONLINE | OFFLINE | BOOTING | SHUTTING_DOWN
let since = new Date().toISOString();
const setState = s => { state = s; since = new Date().toISOString(); };

const SESSION = {
  authenticated: true, csrf: 'mock', user: 'demo', main_name: 'Serwer główny (mock)',
  camera_enabled: false, camera_max_seconds: 60,
  agents: [{ key: 'nas', name: 'NAS' }, { key: 'gpu', name: 'Serwer GPU' }],
};

function status() {
  const up = state === 'ONLINE';
  return {
    stale: ctl.stale, host: '192.168.1.10', state, since,
    icmp_ok: up, icmp_ms: up ? rnd(0.5, 2) : null,
    tcp_ok: up, tcp_ms: up ? rnd(1, 3) : null,
  };
}

function server(key) {
  const agent = SESSION.agents.find(a => a.key === key);
  if (!agent) throw new ApiError('nieznany serwer', 404);
  return {
    name: agent.name,
    state: {
      ok: true, last_ok: new Date().toISOString(), error: null,
      data: {
        hostname: key, os: 'Debian 12', uptime: 3 * 86400 + 4000,
        cpu: { model: 'Intel Core i5-12400', cores: 6, threads: 12, freq_mhz: 2500, percent: rnd(5, 60), load: [0.4, 0.5, 0.6] },
        mem: { percent: rnd(30, 70), used: 10 * GB, total: 32 * GB, swap_total: 4 * GB, swap_used: 0.2 * GB },
        disks: [{ mount: '/', percent: 41, used: 200 * GB, total: 500 * GB, fstype: 'ext4' }],
        gpus: key === 'gpu' ? [{ name: 'RTX 3060', util: rnd(0, 90), mem_used: 4 * GB, mem_total: 12 * GB, temp: rnd(40, 75) }] : [],
        temp_max: rnd(40, 70), temps: [{ label: 'CPU', current: rnd(40, 70) }],
        rates: { rx: rnd(1e4, 5e6), tx: rnd(1e4, 2e6) },
      },
    },
  };
}

function wake() {
  if (state === 'ONLINE') return { ok: false, message: 'Serwer już działa.' };
  setState('BOOTING');
  setTimeout(() => setState('ONLINE'), 5000);
  return { ok: true, message: 'Wysłano magic packet. Czekam na start serwera…' };
}

function shutdown(body) {
  if (!body || body.password !== 'test') return { ok: false, message: 'Nieprawidłowe hasło.' };
  setState('SHUTTING_DOWN');
  setTimeout(() => setState('OFFLINE'), 4000);
  return { ok: true, message: 'Wysłano polecenie wyłączenia.' };
}

// [metoda, wzorzec ścieżki, handler(parametr, body)]
const routes = [
  ['GET', /^\/api\/session$/, () => SESSION],
  ['GET', /^\/api\/status$/, () => status()],
  ['GET', /^\/api\/servers\/([^/]+)$/, key => server(key)],
  ['POST', /^\/api\/actions\/wake$/, () => wake()],
  ['POST', /^\/api\/actions\/shutdown$/, (_, body) => shutdown(body)],
  ['POST', /^\/api\/logout$/, () => ({ ok: true })],
];

export async function mockRequest(method, url, body) {
  await delay(rnd(150, 400));                // udaje opóźnienie sieci
  if (ctl.fail) throw new ApiError('brak połączenia z panelem', 0);
  const path = url.split('?')[0];
  for (const [m, re, fn] of routes) {
    const hit = m === method && path.match(re);
    if (hit) return structuredClone(fn(hit[1], body));
  }
  throw new ApiError(`brak mocka dla ${method} ${path}`, 404);
}