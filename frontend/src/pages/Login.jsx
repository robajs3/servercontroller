import { useState } from 'react';
import { ApiError, post } from '../api.js';
import { useSession } from '../session.jsx';

export default function Login() {
  const { refresh } = useSession();
  const [f, setF] = useState({ username: '', password: '', code: '' });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = k => e => setF({ ...f, [k]: e.target.value });

  const submit = async e => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await post('/api/login', f, { auth: false });
      await refresh();                      // nowa sesja i token CSRF; guard przełączy widok
    } catch (x) {
      setErr(x instanceof ApiError ? x.message : String(x));
      setF(s => ({ ...s, password: '', code: '' }));
      setBusy(false);
    }
  };
  return (
    <form className="card narrow" onSubmit={submit}>
      <h2>Logowanie</h2>
      {err && <p className="err">{err}</p>}
      <input name="username" placeholder="Użytkownik" autoComplete="username" required autoFocus value={f.username} onChange={set('username')} />
      <input name="password" type="password" placeholder="Hasło" autoComplete="current-password" required value={f.password} onChange={set('password')} />
      <input name="code" placeholder="Kod 2FA (6 cyfr)" inputMode="numeric" autoComplete="one-time-code" required value={f.code} onChange={set('code')} />
      <button disabled={busy}>Zaloguj</button>
    </form>
  );
}
