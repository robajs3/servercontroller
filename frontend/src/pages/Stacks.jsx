import { useEffect, useRef, useState } from 'react';
import { action, get, qs } from '../api.js';
import { usePoll } from '../hooks.js';
import { AgentTabs, Msg, Pill, useAgentKey } from '../components/ui.jsx';
import { useSession } from '../session.jsx';

const NEW_TEMPLATE = `services:
  app:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "8081:80"
`;

export default function Stacks() {
  const { agents } = useSession();
  const key = useAgentKey(agents);
  if (!key) return <p className="muted">Brak skonfigurowanych serwerów.</p>;
  return (<><AgentTabs agents={agents} current={key} /><StacksServer key={key} srv={key} /></>);
}

function StacksServer({ srv }) {
  const list = usePoll(() => get(`/api/stacks/${srv}`), [srv], 0);   // odświeżane po utworzeniu stosu
  const [job, setJob] = useState(null);        // {id, stack, action, status, output, rc} albo {error}
  const [edit, setEdit] = useState(null);      // {name, kind}

  const run = async (s, act, confirmText) => {
    if (confirmText && !window.confirm(confirmText)) return;
    const r = await action(`/api/stacks/${srv}/${s.name}/run/${act}`);
    setJob(r.ok ? r.job : { error: r.message });
  };

  const d = list.data;
  return (
    <>
      <section className="card">
        <h3>Stosy docker compose</h3>
        <div>
          {!d ? (list.error ? <p className="err">Agent: {list.error}</p> : <p className="muted">…</p>) : (
            <>
              {(d.error || d.code !== 200) && <p className="err">Agent: {d.error || d.code}</p>}
              <div className="stack-grid">
                {d.stacks.map(s => (
                  <div className="stackcard" key={s.name}>
                    <div className="path"><b>{s.name}</b><br /><span className="muted">{s.path}/{s.file}</span></div>
                    <div className="btns">
                      <button className="ghost sm" onClick={() => setEdit({ name: s.name, kind: 'compose' })}>Edytuj</button>
                      <button className="sm" onClick={() => run(s, 'up', `Wykonać „up -d” dla ${s.name}?`)}>Up</button>
                      <button className="ghost sm" onClick={() => run(s, 'pull')}>Pull</button>
                      <button className="ghost sm" onClick={() => run(s, 'restart', `Zrestartować cały stos ${s.name}?`)}>Restart</button>
                      <button className="danger sm" onClick={() => run(s, 'down', `Wykonać „down” (usuwa kontenery stosu ${s.name}, wolumeny zostają)?`)}>Down</button>
                    </div>
                  </div>
                ))}
              </div>
              {!d.stacks.length && <p className="muted">Brak stosów. Dodaj katalogi w <code>AGENT_STACK_DIRS</code> (agent.env) albo utwórz nowy stos poniżej.</p>}
            </>
          )}
        </div>
        <Job srv={srv} job={job} setJob={setJob} />
      </section>
      <section className="card"><h3>Edytor</h3>
        {edit ? <Editor key={edit.name} srv={srv} name={edit.name} kind={edit.kind} setKind={k => setEdit({ ...edit, kind: k })} />
          : <p className="muted">Wybierz „Edytuj” przy stosie. Zapis wymaga hasła i przechodzi walidację <code>docker compose config</code>; poprzednia wersja trafia do kopii <code>.bak</code>.</p>}
      </section>
      <NewStack srv={srv} onCreated={list.reload} />
    </>
  );
}

// Wynik zadania compose; dopóki trwa, odpytujemy agenta co 2 s
function Job({ srv, job, setJob }) {
  const id = job && job.id, running = job && job.status === 'running';
  useEffect(() => {
    if (!running) return;
    const t = setInterval(async () => {
      try { setJob((await get(`/api/stacks/${srv}/job/${id}`)).job); }
      catch (e) { setJob({ error: `Nie znaleziono zadania (${e.message})` }); }
    }, 2000);
    return () => clearInterval(t);
  }, [running, id, srv, setJob]);
  if (!job) return null;
  if (job.error) return <p className="err">{job.error}</p>;
  return (
    <div>
      <p><b>{job.stack} · {job.action}</b>{' '}
        {job.status === 'running' ? <Pill sm cls="warn">trwa…</Pill>
          : job.rc === 0 ? <Pill sm cls="ok">OK</Pill> : <Pill sm cls="bad">błąd ({job.rc})</Pill>}</p>
      <pre className="log">{job.output}</pre>
    </div>
  );
}

function Editor({ srv, name, kind, setKind }) {
  const [file, setFile] = useState(null);       // {content, exists, file} | {error}
  const [content, setContent] = useState('');
  const [pw, setPw] = useState('');
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    let live = true;
    setFile(null); setMsg(null);
    get(`/api/stacks/${srv}/${name}/file?` + qs({ kind }))
      .then(j => { if (live) { setFile(j); setContent(j.content || ''); } })
      .catch(e => { if (live) setFile({ error: `Nie udało się wczytać pliku: ${e.message}` }); });
    return () => { live = false; };
  }, [srv, name, kind]);

  const save = async e => {
    e.preventDefault();
    setMsg(await action(`/api/stacks/${srv}/${name}/save`, { kind, content, password: pw }));
    setPw('');
  };

  return (
    <>
      <div className="row"><b>{name}</b>
        <button className="ghost sm" onClick={() => setKind('compose')}>{kind === 'compose' ? '● docker-compose' : 'docker-compose'}</button>
        <button className="ghost sm" onClick={() => setKind('env')}>{kind === 'env' ? '● .env' : '.env'}</button></div>
      {!file ? <p className="muted">…</p> : file.error ? <p className="err">{file.error}</p> : (
        <>
          {!file.exists && <p className="muted">Plik {file.file} jeszcze nie istnieje, zapis go utworzy.</p>}
          <form onSubmit={save}>
            <textarea className="code" rows="22" spellCheck="false" value={content} onChange={e => setContent(e.target.value)} />
            <div className="row">
              <input type="password" placeholder="Hasło" autoComplete="current-password" required className="pwin"
                     value={pw} onChange={e => setPw(e.target.value)} />
              <button>Zapisz</button>
            </div>
          </form>
          <Msg msg={msg} />
        </>
      )}
    </>
  );
}

function NewStack({ srv, onCreated }) {
  const [name, setName] = useState('');
  const [content, setContent] = useState(NEW_TEMPLATE);
  const [pw, setPw] = useState('');
  const [msg, setMsg] = useState(null);
  const submit = async e => {
    e.preventDefault();
    const r = await action(`/api/stacks/${srv}/new`, { name, content, password: pw });
    setMsg(r); setPw('');
    if (r.ok) onCreated();
  };
  return (
    <section className="card">
      <details><summary><b>Nowy stos</b></summary>
        <form onSubmit={submit}>
          <input placeholder="nazwa (np. moja-apka)" pattern="[a-z0-9][a-z0-9_\-]{0,40}" required value={name} onChange={e => setName(e.target.value)} />
          <textarea className="code" rows="12" spellCheck="false" required value={content} onChange={e => setContent(e.target.value)} />
          <input type="password" placeholder="Hasło" autoComplete="current-password" required value={pw} onChange={e => setPw(e.target.value)} />
          <button>Utwórz</button>
        </form>
        <Msg msg={msg} />
      </details>
    </section>
  );
}
