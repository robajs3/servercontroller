// Klient API panelu. Token CSRF pobieramy z /api/session; wygasła sesja (401) wraca do ekranu logowania.
let csrf = '';
let onUnauthorized = () => {};

export const setCsrf = t => { csrf = t || ''; };
export const setUnauthorizedHandler = fn => { onUnauthorized = fn; };

export class ApiError extends Error {
  constructor(message, status, body) { super(message); this.status = status; this.body = body; }
}

export async function request(method, url, body, { auth = true } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET') headers['X-CSRFToken'] = csrf;
  let r;
  try {
    r = await fetch(url, { method, headers, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError('brak połączenia z panelem', 0);
  }
  const j = await r.json().catch(() => null);
  if (r.status === 401 && auth) { onUnauthorized(); throw new ApiError('sesja wygasła', 401, j); }
  if (!r.ok) throw new ApiError((j && (j.error || j.message)) || 'HTTP ' + r.status, r.status, j);
  return j;
}

export const get = url => request('GET', url);
export const post = (url, body = {}, opts) => request('POST', url, body, opts);

// Akcje zwracające {ok, message}: błędy biznesowe (4xx z message) nie rzucają, tylko wracają jako {ok:false}.
export async function action(url, body = {}) {
  try {
    const j = await post(url, body);
    return { ok: j.ok !== false, message: j.message, ...j };
  } catch (e) {
    if (e instanceof ApiError && e.body && typeof e.body === 'object' && ('message' in e.body || e.body.validation)) {
      return { ok: false, ...e.body };
    }
    return { ok: false, message: e.message };
  }
}

export const qs = o => new URLSearchParams(o).toString();
