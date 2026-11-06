import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { SessionProvider, useSession } from './session.jsx';
import Layout from './components/Layout.jsx';
import Login from './pages/Login.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Docker from './pages/Docker.jsx';
import Stacks from './pages/Stacks.jsx';
import Camera from './pages/Camera.jsx';
import Notifications from './pages/Notifications.jsx';

function Routed() {
  const { authenticated } = useSession();
  if (!authenticated) {
    return <main><Routes><Route path="/login" element={<Login />} /><Route path="*" element={<Navigate to="/login" replace />} /></Routes></main>;
  }
  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="docker" element={<Docker />} />
        <Route path="stacks" element={<Stacks />} />
        <Route path="camera" element={<Camera />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return <BrowserRouter><SessionProvider><Routed /></SessionProvider></BrowserRouter>;
}
