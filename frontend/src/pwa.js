// PWA: service worker, instalacja i powiadomienia push (port dawnego static/pwa.js).
// Bez inline JS i bez zewnętrznych zasobów (CSP).
import { get, post } from './api.js';

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* tryb prywatny */ } },
};

export const standalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
export const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
export const hasSW = 'serviceWorker' in navigator;
export const hasPush = hasSW && 'PushManager' in window && 'Notification' in window;

export function registerSW() {
  if (!hasSW) return;
  const reg = () => navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
  if (document.readyState === 'complete') reg(); else addEventListener('load', reg);
}

export const snooze = {
  active: () => Date.now() - Number(store.get('pwa-snooze') || 0) < 14 * 864e5,
  set: () => store.set('pwa-snooze', Date.now()),
};

const b64u = s => {
  const b = atob((s + '='.repeat((4 - s.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(b, c => c.charCodeAt(0));
};
const sameKey = (sub, key) => {
  const a = sub.options && sub.options.applicationServerKey; if (!a) return false;
  const x = new Uint8Array(a), y = b64u(key);
  return x.length === y.length && x.every((v, i) => v === y[i]);
};

export const getSub = async () => (await navigator.serviceWorker.ready).pushManager.getSubscription();

export async function enablePush() {
  const cfg = await get('/api/push/key');
  if (!cfg.configured) throw new Error('Serwer nie ma kluczy VAPID (patrz README: Powiadomienia push).');
  if (await Notification.requestPermission() !== 'granted') throw new Error('Brak zgody na powiadomienia w przeglądarce.');
  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(sub, cfg.key)) { await sub.unsubscribe(); sub = null; }   // subskrypcja pod starym kluczem VAPID
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64u(cfg.key) });
  await post('/api/push/subscribe', sub.toJSON());
  store.set('push-pref', 'on');
}

export async function disablePush() {
  const sub = await getSub();
  store.set('push-pref', 'off');
  if (sub) { const ep = sub.endpoint; await sub.unsubscribe().catch(() => {}); await post('/api/push/unsubscribe', { endpoint: ep }); }
}

export async function testPush() {
  const j = await post('/api/push/test');
  if (!j.sent) throw new Error('Nie dostarczono testu. Sprawdź klucze VAPID i VAPID_SUBJECT w .env oraz logi kontenera web.');
}

// Przy zwykłych odwiedzinach (raz na 12 h) synchronizujemy subskrypcję z serwerem; jeśli przeglądarka ją zgubiła,
// a użytkownik jej nie wyłączył, odnawiamy ją po cichu.
export async function resyncPush() {
  if (!hasPush || Notification.permission !== 'granted' || store.get('push-pref') !== 'on') return;
  if (Date.now() - Number(store.get('push-sync') || 0) < 12 * 3600e3) return;
  try { await enablePush(); store.set('push-sync', Date.now()); } catch { /* spróbujemy przy następnej wizycie */ }
}
