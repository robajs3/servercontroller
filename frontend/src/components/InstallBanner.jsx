import { useEffect, useRef, useState } from 'react';
import { isIOS, snooze, standalone } from '../pwa.js';

export default function InstallBanner() {
  const [b, setB] = useState(null);   // {text, canInstall}
  const deferred = useRef(null);

  useEffect(() => {
    const show = (text, canInstall) => { if (!standalone() && !snooze.active()) setB({ text, canInstall }); };
    const onPrompt = e => { e.preventDefault(); deferred.current = e; show('Zainstaluj panel jako aplikację na tym urządzeniu.', true); };
    const onInstalled = () => setB(null);
    addEventListener('beforeinstallprompt', onPrompt);
    addEventListener('appinstalled', onInstalled);
    if (isIOS && !standalone()) show('Aby zainstalować panel i włączyć powiadomienia: Udostępnij → Do ekranu początkowego (iOS 16.4+).', false);
    return () => { removeEventListener('beforeinstallprompt', onPrompt); removeEventListener('appinstalled', onInstalled); };
  }, []);

  if (!b) return null;
  const install = async () => {
    const p = deferred.current; if (!p) return;
    p.prompt(); await p.userChoice.catch(() => {}); deferred.current = null; setB(null);
  };
  return (
    <div className="banner">
      <span>{b.text}</span>
      {b.canInstall && <button className="sm" onClick={install}>Zainstaluj</button>}
      <button className="ghost sm" onClick={() => { snooze.set(); setB(null); }}>✕</button>
    </div>
  );
}
