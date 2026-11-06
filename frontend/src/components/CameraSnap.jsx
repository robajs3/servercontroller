import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';

// Podgląd kamery na pulpicie: odświeżany co 10 s, tylko gdy karta jest widoczna.
export default function CameraSnap() {
  const img = useRef(null);
  useEffect(() => {
    const t = setInterval(() => {
      if (document.visibilityState === 'visible' && img.current) img.current.src = '/camera/snapshot?t=' + Date.now();
    }, 10000);
    return () => clearInterval(t);
  }, []);
  return (
    <section className="card">
      <div className="row"><h3>Kamera</h3><Link className="tab" to="/camera">Na żywo</Link></div>
      <img ref={img} className="cam" alt="Podgląd kamery" src="/camera/snapshot" />
    </section>
  );
}
