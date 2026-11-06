import { useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useSession } from '../session.jsx';
import InstallBanner from './InstallBanner.jsx';
import { resyncPush } from '../pwa.js';

const ICONS = {
  servers: <><rect x="2" y="3" width="20" height="8" rx="2" /><rect x="2" y="13" width="20" height="8" rx="2" /><line x1="6" y1="7" x2="6.01" y2="7" /><line x1="6" y1="17" x2="6.01" y2="17" /></>,
  docker: <><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" /><path d="m3.3 7 8.7 5 8.7-5" /><path d="M12 22V12" /></>,
  stacks: <><path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z" /><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65" /><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65" /></>,
  camera: <><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" /><circle cx="12" cy="13" r="3" /></>,
  bell: <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></>,
  logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></>,
};

const Icon = ({ n }) => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICONS[n]}</svg>
);

export default function Layout() {
  const { camera_enabled, logout } = useSession();
  useEffect(() => { resyncPush(); }, []);

  // [ścieżka, ikona, pełna etykieta (lewy pasek), krótka etykieta (dolna nawigacja)]
  const items = [
    ['/', 'servers', 'Serwery', 'Serwery'],
    ['/docker', 'docker', 'Docker', 'Docker'],
    ['/stacks', 'stacks', 'Stosy', 'Stosy'],
    ...(camera_enabled ? [['/camera', 'camera', 'Kamera', 'Kamera']] : []),
    ['/notifications', 'bell', 'Powiadomienia', 'Alerty'],
  ];
  const cls = ({ isActive }) => (isActive ? 'active' : undefined);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand"><i><Icon n="servers" /></i>Panel</div>
        <nav>
          {items.map(([to, ic, label]) => (
            <NavLink key={to} to={to} end={to === '/'} className={cls}><Icon n={ic} />{label}</NavLink>
          ))}
        </nav>
        <div className="spacer" />
        <button className="ghost" onClick={logout}><Icon n="logout" />Wyloguj</button>
      </aside>

      <div className="content">
        <InstallBanner />
        <header className="topbar">
          <div className="brand"><i><Icon n="servers" /></i>Panel</div>
          <button className="ghost sm" onClick={logout}>Wyloguj</button>
        </header>
        <main><Outlet /></main>
      </div>

      <nav className="bottomnav" aria-label="Nawigacja">
        {items.map(([to, ic, , short]) => (
          <NavLink key={to} to={to} end={to === '/'} className={cls}><Icon n={ic} /><span>{short}</span></NavLink>
        ))}
      </nav>
    </div>
  );
}
