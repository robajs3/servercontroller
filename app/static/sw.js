// Service worker panelu: powiadomienia push i strona offline.
// Celowo NIE zapisuje w cache stron ani API panelu: to dane zależne od sesji i sterowanie sprzętem.
const CACHE = 'panel-offline-v1';
const OFFLINE = '/static/offline.html';

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.add(OFFLINE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Tylko nawigacje: gdy panel jest nieosiągalny, pokazujemy stronę offline zamiast błędu przeglądarki.
self.addEventListener('fetch', e => {
  if (e.request.mode !== 'navigate') return;
  e.respondWith(fetch(e.request).catch(() => caches.match(OFFLINE)));
});

// Adres z powiadomienia traktujemy tylko jako ścieżkę w obrębie panelu.
const safePath = u => (typeof u === 'string' && u.startsWith('/') && !u.startsWith('//')) ? u : '/';

self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = {body: e.data ? e.data.text() : ''}; }
  e.waitUntil(self.registration.showNotification(d.title || 'Panel serwerów', {
    body: d.body || '',
    tag: d.tag || undefined,                       // ten sam tag: „ustąpił” podmienia „wystąpił” zamiast dokładać drugie
    renotify: !!(d.urgent && d.tag),               // nowy alert pod tym samym tagiem znów dzwoni
    requireInteraction: !!d.urgent,                // alerty nie znikają same (tam, gdzie system na to pozwala)
    icon: '/static/pwa/icon-192.png',
    badge: '/static/pwa/badge-96.png',
    data: {url: safePath(d.url)},
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = new URL(safePath(e.notification.data && e.notification.data.url), self.location.origin).href;
  e.waitUntil(clients.matchAll({type: 'window', includeUncontrolled: true}).then(list => {
    const open = list.find(c => c.url.startsWith(self.location.origin) && 'focus' in c);
    if (!open) return clients.openWindow(url);
    return open.focus().then(c => (c && 'navigate' in c) ? c.navigate(url) : c);
  }));
});
