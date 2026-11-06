import { useCallback, useEffect, useRef, useState } from 'react';

// Cykliczne pobieranie danych: tylko gdy karta jest widoczna, natychmiast po powrocie na kartę
// i na żądanie (reload). Zwraca {data, error, loading, reload}.
export function usePoll(fn, deps, intervalMs) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const alive = useRef(true);
  const seq = useRef(0);

  const reload = useCallback(async () => {
    const my = ++seq.current;
    try {
      const data = await fnRef.current();
      if (alive.current && my === seq.current) setState({ data, error: null, loading: false });
    } catch (e) {
      if (alive.current && my === seq.current) setState(s => ({ ...s, error: e.message || String(e), loading: false }));
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    setState(s => ({ ...s, loading: true }));
    reload();
    let t;
    if (intervalMs) t = setInterval(() => { if (!document.hidden) reload(); }, intervalMs);
    const vis = () => { if (!document.hidden && intervalMs) reload(); };
    document.addEventListener('visibilitychange', vis);
    return () => { alive.current = false; clearInterval(t); document.removeEventListener('visibilitychange', vis); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, intervalMs]);

  return { ...state, reload };
}

// Stan komunikatu akcji {ok, message}
export function useMsg() {
  const [msg, setMsg] = useState(null);
  return [msg, setMsg];
}
