// Wspólne funkcje frontendu panelu.

// Pobiera JSON z API. Wygasła sesja (401) przenosi do logowania zamiast wywalać .json().
async function api(url) {
  const r = await fetch(url, {headers: {Accept: 'application/json'}, credentials: 'same-origin'});
  if (r.status === 401 || (r.redirected && r.url.includes('/login'))) {
    location.href = '/login';
    throw new Error('sesja wygasła');
  }
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

// Wykonuje fn(); przy błędzie pokazuje komunikat w elemencie #errId i zwraca null.
async function guarded(errId, fn) {
  const el = document.getElementById(errId);
  try {
    const v = await fn();
    if (el) el.hidden = true;
    return v;
  } catch (e) {
    if (el) { el.textContent = 'Nie udało się pobrać danych: ' + e.message; el.hidden = false; }
    return null;
  }
}

// Czasy z serwera (<time class="lt" datetime="...">) pokazujemy w strefie przeglądarki użytkownika.
function localize(root) {
  const scope = root && root.querySelectorAll ? root : document;
  const nodes = [...scope.querySelectorAll('time.lt')];
  if (scope.matches && scope.matches('time.lt')) nodes.push(scope);
  const p = n => String(n).padStart(2, '0');
  for (const t of nodes) {
    const d = new Date(t.getAttribute('datetime'));
    if (!isNaN(d)) t.textContent = `${p(d.getDate())}.${p(d.getMonth() + 1)} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }
}
document.addEventListener('DOMContentLoaded', () => localize(document));
document.addEventListener('htmx:load', e => localize(e.target));   // po każdej podmianie fragmentu przez htmx

// Cykliczne odświeżanie fragmentów (htmx): zamiast "every Ns [warunek]" (filtry htmx wymagają eval,
// zablokowanego przez CSP) wysyłamy zdarzenia tick5/tick10/tick30 na <body>, tylko gdy karta jest widoczna.
const TICKS = [5, 10, 30];
function tickNow(n) {
  if (!document.hidden) document.body.dispatchEvent(new CustomEvent('tick' + n));
}
document.addEventListener('DOMContentLoaded', () => TICKS.forEach(n => setInterval(() => tickNow(n), n * 1000)));
document.addEventListener('visibilitychange', () => { if (!document.hidden) TICKS.forEach(tickNow); });

// Przycisk z data-clear="#selektor" czyści wskazany element (bez inline onclick, którego CSP nie dopuszcza).
document.addEventListener('click', e => {
  const b = e.target.closest && e.target.closest('[data-clear]');
  const t = b && document.querySelector(b.dataset.clear);
  if (t) t.innerHTML = '';
});
