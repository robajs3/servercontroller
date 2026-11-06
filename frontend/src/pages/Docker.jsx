import { useEffect, useMemo, useState } from 'react';
import { action, get, qs } from '../api.js';
import { usePoll } from '../hooks.js';
import { fmtShort, uptime, mb } from '../format.js';
import { AgentTabs, Loading, Msg, Pill, RangeButtons, Time, useAgentKey } from '../components/ui.jsx';
import { useSession } from '../session.jsx';

const EVENT_LABEL = { seen: 'wykryty', up: 'uruchomiony', stop: 'zatrzymany', crash: 'AWARIA', restart: 'restart', oom: 'OOM', unhealthy: 'niezdrowy', healthy: 'zdrowy', gone: 'usunięty' };
const eventCls = k => (['crash', 'oom', 'unhealthy'].includes(k) ? 'bad' : ['up', 'healthy'].includes(k) ? 'ok' : 'gray');

export default function Docker() {
  const { agents } = useSession();
  const key = useAgentKey(agents);
  if (!key) return <p className="muted">Brak skonfigurowanych serwerów.</p>;
  return (<><AgentTabs agents={agents} current={key} /><DockerServer key={key} srv={key} /></>);
}

function DockerServer({ srv }) {
  const [rev, setRev] = useState(0);                 // „refresh-docker”: po akcji odświeża kontenery i zdarzenia
  const bump = () => setRev(r => r + 1);
  const [msg, setMsg] = useState(null);
  const [logs, setLogs] = useState(null);

  const cs = usePoll(() => get(`/api/docker/${srv}/containers`), [srv, rev], 10000);
  const evs = usePoll(() => get(`/api/docker/${srv}/events`), [srv, rev], 30000);

  const act = async (c, a) => {
    setMsg(await action(`/api/docker/${srv}/c/${c.id}/${a}`));
    bump();
  };
  const confirmAct = (c, a) => {
    const q = a === 'restart' ? `Zrestartować ${c.name}?`
      : `Zatrzymać ${c.name}?${c.state === 'restarting' ? ' Kontener jest w pętli restartów, Stop przerwie ją i wyłączy go na stałe (do ręcznego Startu).' : ''}`;
    if (window.confirm(q)) act(c, a);
  };
  const showLogs = async c => {
    try { setLogs((await get(`/api/docker/${srv}/c/${c.id}/logs`)).text); }
    catch (e) { setLogs('Błąd: ' + e.message); }
  };

  return (
    <>
      <section className="card">
        <h3>Kontenery</h3>
        <Msg msg={msg} />
        <div className="scroll"><ContainerTable res={cs} onStart={c => act(c, 'start')} onConfirm={confirmAct} onLogs={showLogs} /></div>
        {logs !== null && (
          <div>
            <p className="muted">Logi (ostatnie linie) <button className="ghost sm" onClick={() => setLogs(null)}>zamknij</button></p>
            <pre className="log">{logs}</pre>
          </div>
        )}
      </section>
      <Timeline srv={srv} />
      <section className="card"><h3>Zdarzenia</h3>
        {!evs.data ? <Loading error={evs.error} /> : !evs.data.length ? <p className="muted">Brak zdarzeń.</p> : (
          <div className="scroll"><table className="rtable flow"><tbody>
            {evs.data.map((e, i) => (
              <tr key={i}><td className="muted"><Time iso={e.ts} /></td><td><b>{e.name}</b></td>
                <td><Pill sm cls={eventCls(e.kind)}>{EVENT_LABEL[e.kind] || e.kind}</Pill></td>
                <td className="muted">{e.detail || ''}</td></tr>
            ))}
          </tbody></table></div>
        )}
      </section>
    </>
  );
}

function ContainerTable({ res, onStart, onConfirm, onLogs }) {
  const { data, error } = res;
  if (!data) return <Loading error={error} />;
  const { state: st, containers: cs } = data;
  if (!st) return <p className="muted">Brak danych Dockera. Worker pobierze je w ciągu ~30 s.</p>;
  const nowMs = Date.now();
  return (
    <>
      {!st.ok && <p className="err">Docker/agent niedostępny: {st.error}{st.has_data && <> (ostatnie znane dane z <Time iso={st.checked} />)</>}</p>}
      {cs.length > 0 ? (
        <table className="rtable">
          <thead><tr><th>Kontener</th><th>Stan</th><th>CPU</th><th>RAM</th><th>Restarty</th><th></th></tr></thead>
          <tbody>
            {cs.map(c => (
              <tr key={c.id}>
                <td className="full"><b>{c.name}</b><br /><span className="muted">{c.project || '–'} · {c.image}{c.ports && c.ports.length ? ` · ${c.ports.join(', ')}` : ''}</span></td>
                <td data-label="Stan"><div><Pill sm cls={c.cls}>{c.state}</Pill>{' '}
                  {c.health && <span className="muted">{c.health}</span>}
                  {c.up_since ? <><br /><span className="muted">od {uptime((nowMs - new Date(c.up_since).getTime()) / 1000)}</span></>
                    : c.exit_code != null && c.state !== 'created' ? <><br /><span className="muted">kod {c.exit_code}{c.oom ? ' · OOM' : ''}</span></> : null}</div></td>
                <td data-label="CPU">{c.cpu !== undefined ? `${c.cpu.toFixed(1)}%` : '–'}</td>
                <td data-label="RAM">{c.mem !== undefined ? mb(c.mem) : '–'}</td>
                <td data-label="Restarty">{c.restarts}</td>
                <td className="acts">
                  {c.state !== 'running' && <button className="sm" onClick={() => onStart(c)}>Start</button>}
                  {['running', 'restarting', 'paused'].includes(c.state) && !c.protected && (
                    <>
                      <button className="ghost sm" onClick={() => onConfirm(c, 'restart')}>Restart</button>
                      <button className="danger sm" onClick={() => onConfirm(c, 'stop')}>Stop</button>
                    </>
                  )}
                  <button className="ghost sm" onClick={() => onLogs(c)}>Logi</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : st.ok && <p className="muted">Brak kontenerów.</p>}
    </>
  );
}

function Timeline({ srv }) {
  const [range, setRange] = useState('24h');
  const { data, error } = usePoll(() => get('/api/docker/timeline?' + qs({ server: srv, range })), [srv, range], 30000);
  const geo = useMemo(() => {
    if (!data) return null;
    const a = new Date(data.from).getTime(), span = new Date(data.to).getTime() - a;
    return t => Math.max(0, Math.min(100, (new Date(t).getTime() - a) / span * 100));
  }, [data]);
  return (
    <section className="card">
      <div className="row"><h3>Oś czasu</h3><RangeButtons ranges={['6h', '24h', '7d', '30d']} value={range} onChange={setRange} cls="sm" /></div>
      {error && <p className="err">Nie udało się pobrać danych: {error}</p>}
      <div>
        {data && !data.rows.length && <p className="muted">Brak danych. Zdarzenia zbiera worker od swojego uruchomienia.</p>}
        {data && data.rows.map(r => (
          <div className="tl-row" key={r.name}>
            <div className="tl-name" title={r.name}>{r.name}</div>
            <div className="tl-bar">
              {r.segs.map(([s, e, st], i) => (
                <i key={i} className={`s-${st}`} style={{ left: geo(s) + '%', width: Math.max(geo(e) - geo(s), .4) + '%' }}
                   title={`${st}: ${fmtShort(s)} → ${fmtShort(e)}`} />
              ))}
              {r.marks.map(([t, k], i) => <b key={i} style={{ left: geo(t) + '%' }} title={`${k} ${fmtShort(t)}`} />)}
            </div>
          </div>
        ))}
      </div>
      <p className="muted"><span className="dot s-up" /> działa <span className="dot s-crashed" /> awaria <span className="dot s-stopped" /> zatrzymany <span className="dot s-mark" /> restart / OOM</p>
    </section>
  );
}
