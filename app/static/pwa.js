// PWA: service worker, baner instalacji i powiadomienia push.
// Bez inline JS i bez zewnętrznych zasobów (CSP). Ekran „Powiadomienia” podpina się pod elementy #push-*.
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (_) {} },
  };
  const standalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const hasSW = 'serviceWorker' in navigator;
  const hasPush = hasSW && 'PushManager' in window && 'Notification' in window;

  if (hasSW) addEventListener('load', () => navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(() => {}));

  // ---------- baner „Zainstaluj aplikację” ----------
  const banner = $('#install-banner');
  let deferred = null;
  const snoozed = () => Date.now() - Number(store.get('pwa-snooze') || 0) < 14 * 864e5;
  function showBanner(text, canInstall) {
    if (!banner || standalone() || snoozed()) return;
    $('#install-text').textContent = text;
    $('#install-btn').hidden = !canInstall;
    banner.hidden = false;
  }
  addEventListener('beforeinstallprompt', e => {
    e.preventDefault(); deferred = e;
    showBanner('Zainstaluj panel jako aplikację na tym urządzeniu.', true);
  });
  addEventListener('appinstalled', () => { if (banner) banner.hidden = true; });
  if (banner) {
    $('#install-btn').onclick = async () => {
      if (!deferred) return;
      deferred.prompt(); await deferred.userChoice.catch(() => {}); deferred = null; banner.hidden = true;
    };
    $('#install-x').onclick = () => { store.set('pwa-snooze', Date.now()); banner.hidden = true; };
    if (isIOS && !standalone()) {
      showBanner('Aby zainstalować panel i włączyć powiadomienia: Udostępnij → Do ekranu początkowego (iOS 16.4+).', false);
    }
  }

  // ---------- push ----------
  const csrf = () => ($('meta[name=csrf-token]') || {}).content || '';
  async function post(url, body) {
    const r = await fetch(url, {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: JSON.stringify(body || {})});
    if (r.status === 401) { location.href = '/login'; throw new Error('sesja wygasła'); }
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status);
    return j;
  }
  const b64u = s => { const b = atob((s + '='.repeat((4 - s.length % 4) % 4)).replace(/-/g, '+').replace(/_/g, '/')); return Uint8Array.from(b, c => c.charCodeAt(0)); };
  const sameKey = (sub, key) => {
    const a = sub.options && sub.options.applicationServerKey; if (!a) return false;
    const x = new Uint8Array(a), y = b64u(key);
    return x.length === y.length && x.every((v, i) => v === y[i]);
  };
  const getSub = async () => (await navigator.serviceWorker.ready).pushManager.getSubscription();

  async function enable() {
    const cfg = await (await fetch('/api/push/key', {credentials: 'same-origin'})).json();
    if (!cfg.configured) throw new Error('Serwer nie ma kluczy VAPID (patrz README: Powiadomienia push).');
    if (await Notification.requestPermission() !== 'granted') throw new Error('Brak zgody na powiadomienia w przeglądarce.');
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (sub && !sameKey(sub, cfg.key)) { await sub.unsubscribe(); sub = null; }   // subskrypcja pod starym kluczem VAPID
    if (!sub) sub = await reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: b64u(cfg.key)});
    await post('/api/push/subscribe', sub.toJSON());
    store.set('push-pref', 'on');
  }
  async function disable() {
    const sub = await getSub();
    store.set('push-pref', 'off');
    if (sub) { const ep = sub.endpoint; await sub.unsubscribe().catch(() => {}); await post('/api/push/unsubscribe', {endpoint: ep}); }
  }

  // Przy zwykłych odwiedzinach (raz na 12 h) synchronizujemy subskrypcję z serwerem; jeśli przeglądarka ją zgubiła,
  // a użytkownik jej nie wyłączył, odnawiamy ją po cichu.
  async function resync() {
    if (!hasPush || !$('#install-banner') || Notification.permission !== 'granted' || store.get('push-pref') !== 'on') return;
    if (Date.now() - Number(store.get('push-sync') || 0) < 12 * 3600e3) return;
    try { await enable(); store.set('push-sync', Date.now()); } catch (_) {}
  }

  async function initUI() {
    const ui = $('#push-ui'); if (!ui) return;
    const st = $('#push-status'), err = $('#push-err'), on = $('#push-on'), off = $('#push-off'), test = $('#push-test');
    const show = (text, {bOn = false, bOff = false} = {}) => { st.textContent = text; on.hidden = !bOn; off.hidden = !bOff; test.hidden = !bOff; };
    const fail = e => { err.textContent = e.message || String(e); err.hidden = false; };
    async function render() {
      err.hidden = true;
      if (!hasPush) {
        show(isIOS && !standalone()
          ? 'Na iPhonie i iPadzie powiadomienia działają tylko w zainstalowanej aplikacji: Udostępnij → Do ekranu początkowego, a potem otwórz panel z ikony (iOS 16.4+).'
          : 'Ta przeglądarka nie obsługuje powiadomień push.');
        return;
      }
      if (Notification.permission === 'denied') { show('Powiadomienia są zablokowane w ustawieniach przeglądarki dla tej strony. Odblokuj je i odśwież stronę.'); return; }
      const sub = await getSub().catch(() => null);
      if (sub && Notification.permission === 'granted') show('Powiadomienia są włączone na tym urządzeniu.', {bOff: true});
      else show('Powiadomienia są wyłączone na tym urządzeniu.', {bOn: true});
    }
    const run = fn => async () => { try { await fn(); } catch (e) { fail(e); } await render(); };
    on.onclick = run(enable);
    off.onclick = run(disable);
    test.onclick = run(async () => {
      const j = await post('/api/push/test');
      if (!j.sent) throw new Error('Nie dostarczono testu. Sprawdź klucze VAPID i VAPID_SUBJECT w .env oraz logi kontenera web.');
    });
    document.addEventListener('click', async e => {
      const b = e.target.closest('[data-del-sub]'); if (!b) return;
      if (!confirm('Usunąć to urządzenie z powiadomień?')) return;
      try { await post('/api/push/delete', {id: Number(b.dataset.delSub)}); location.reload(); } catch (x) { fail(x); }
    });
    render();
  }

  document.addEventListener('DOMContentLoaded', () => { initUI(); resync(); });
})();
