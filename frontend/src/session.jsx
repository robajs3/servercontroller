import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { get, post, setCsrf, setUnauthorizedHandler } from './api.js';

const Ctx = createContext(null);
export const useSession = () => useContext(Ctx);

export function SessionProvider({ children }) {
  const [s, setS] = useState(null);       // null = jeszcze nie wiemy
  const [fatal, setFatal] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const j = await get('/api/session');
      setCsrf(j.csrf);
      setS(j); setFatal(null);
      return j;
    } catch (e) { setFatal(e.message); }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setS(prev => (prev && prev.authenticated ? { ...prev, authenticated: false } : prev)));
    refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    try { await post('/api/logout'); } catch { /* sesja i tak wygasła */ }
    await refresh();
  }, [refresh]);

  if (fatal) return (
    <div className="card narrow"><h2>Brak połączenia</h2><p className="err">{fatal}</p>
      <button onClick={refresh}>Spróbuj ponownie</button></div>
  );
  if (!s) return <p className="muted" style={{ textAlign: 'center', marginTop: '20vh' }}>…</p>;
  return <Ctx.Provider value={{ ...s, refresh, logout }}>{children}</Ctx.Provider>;
}
