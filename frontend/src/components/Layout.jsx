import { useEffect } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { useSession } from '../session.jsx';
import InstallBanner from './InstallBanner.jsx';
import { resyncPush } from '../pwa.js';

export default function Layout() {
  const { camera_enabled, logout } = useSession();
  useEffect(() => { resyncPush(); }, []);
  return (
    <>
      <InstallBanner />
      <header>
        <nav className="row"><b>Panel</b>
          <Link to="/">Serwery</Link>
          <Link to="/docker">Docker</Link>
          <Link to="/stacks">Stosy</Link>
          {camera_enabled && <Link to="/camera">Kamera</Link>}
          <Link to="/notifications">Powiadomienia</Link>
        </nav>
        <button className="ghost" onClick={logout}>Wyloguj</button>
      </header>
      <main><Outlet /></main>
    </>
  );
}
