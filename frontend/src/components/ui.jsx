import { Link, useSearchParams } from 'react-router-dom';
import { fmtTime } from '../format.js';

export const Pill = ({ cls, sm, children }) => <span className={`pill ${sm ? 'sm ' : ''}${cls || ''}`}>{children}</span>;

export const Bar = ({ p }) => (
  <div className="bar"><i className={p >= 90 ? 'hot' : ''} style={{ width: `${Math.min(p || 0, 100)}%` }} /></div>
);

export const Time = ({ iso }) => <time dateTime={iso || undefined}>{fmtTime(iso)}</time>;

// Komunikat akcji: {ok, message} albo walidacja compose ({validation, output})
export function Msg({ msg }) {
  if (!msg) return null;
  if (msg.validation) {
    return (<><p className="err">Walidacja nie przeszła, plik NIE został zapisany:</p><pre className="log">{msg.output}</pre></>);
  }
  return <p className={msg.ok ? 'ok-t' : 'err'}>{msg.message}</p>;
}

export function RangeButtons({ ranges, value, onChange, cls = '' }) {
  return ranges.map(r => (
    <button key={r} className={`ghost ${cls} ${r === value ? 'on' : ''}`} onClick={() => onChange(r)}>{r}</button>
  ));
}

// Zakładki serwerów (agentów) z parametrem ?s=klucz, jak w oryginale
export function useAgentKey(agents) {
  const [sp] = useSearchParams();
  const k = sp.get('s');
  return agents.find(a => a.key === k) ? k : agents[0] && agents[0].key;
}

export function AgentTabs({ agents, current }) {
  return (
    <div className="row tabs">
      {agents.map(a => <Link key={a.key} className={`tab ${a.key === current ? 'on' : ''}`} to={`?s=${a.key}`}>{a.name}</Link>)}
    </div>
  );
}

export const Loading = ({ error }) => error
  ? <p className="err">Nie udało się pobrać danych: {error}</p>
  : <p className="muted">…</p>;
