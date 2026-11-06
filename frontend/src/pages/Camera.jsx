import { useCallback, useEffect, useRef, useState } from 'react';
import { useSession } from '../session.jsx';

const SNAP = '/camera/snapshot', STREAM = '/camera/stream';

export default function Camera() {
  const { camera_enabled, camera_max_seconds: MAX } = useSession();
  const img = useRef(null);
  const timer = useRef(null);
  const live = useRef(false);
  const [status, setStatus] = useState('');
  const [snapSrc, setSnapSrc] = useState(SNAP);

  const stop = useCallback(() => {
    clearTimeout(timer.current); live.current = false;
    setSnapSrc(`${SNAP}?t=${Date.now()}`);
    setStatus('Zatrzymano (widoczne zdjęcie).');
  }, []);
  const start = () => {
    clearTimeout(timer.current); live.current = true;
    setSnapSrc(`${STREAM}?t=${Date.now()}`);
    setStatus(`Na żywo. Podgląd zatrzyma się po zmianie karty lub po ${Math.round(MAX / 60)} min.`);
    timer.current = setTimeout(stop, MAX * 1000);
  };

  useEffect(() => {
    const vis = () => { if (document.hidden && live.current) stop(); };
    document.addEventListener('visibilitychange', vis);
    // zamknięcie widoku zwalnia slot strumienia po stronie serwera (przerwanie połączenia)
    return () => { document.removeEventListener('visibilitychange', vis); clearTimeout(timer.current); if (img.current) img.current.src = ''; };
  }, [stop]);

  if (!camera_enabled) return <p className="muted">Kamera jest wyłączona w konfiguracji panelu.</p>;
  return (
    <section className="card">
      <div className="row"><h3>Kamera</h3>
        <button onClick={start}>▶ Na żywo</button><button className="ghost" onClick={stop}>■ Stop</button>
        <button className="ghost" onClick={stop}>Odśwież zdjęcie</button>
        <a className="tab" href={`${SNAP}?download=1`}>Pobierz zdjęcie</a></div>
      <img ref={img} className="cam" alt="Podgląd kamery" src={snapSrc}
           onError={() => { live.current = false; setStatus('Kamera niedostępna lub zbyt wiele podglądów naraz.'); }} />
      <p className="muted">{status}</p>
    </section>
  );
}
