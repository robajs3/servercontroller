import { Link, useSearchParams } from 'react-router-dom';
import { fmtTime } from '../format.js';
import { useNow } from '../hooks.js';

export const Pill = ({ cls, sm, children }) => <span className={`pill ${sm ? 'sm ' : ''}${cls || ''}`}>{children}</span>;

export const Bar = ({ p }) => (
  <div className="bar"><i className={p >= 90 ? 'hot' : ''} style={{ width: `${Math.min(p || 0, 100)}%` }} /></div>
);

// Kafelek metryki: etykieta, duża wartość, opis i opcjonalny pasek
export const Tile = ({ label, value, sub, p, wide, children }) => (
  <div className={`tile${wide ? ' wide' : ''}`}>
    <span className="t-label">{label}</span>
    {value !== undefined && <b className="t-val">{value}</b>}
    {children}
    {sub ? <span className="t-sub muted">{sub}</span> : null}
    {p != null && <Bar p={p} />}
  </div>
);

export const Time = ({ iso }) => <time dateTime={iso || undefined}>{fmtTime(iso)}</time>;

// "Zaktualizowano X s temu"; przy błędzie odświeżania pokazuje wiek ostatnich udanych danych
export function Updated({ at, error }) {
  const now = useNow();
  if (!at) return null;
  const s = Math.max(0, Math.round((now - at) / 1000));
  const ago = s < 60 ? `${s} s` : `${Math.floor(s / 60)} min`;
  return (
    <p className={`updated ${error ? 'err' : 'muted'}`}>
      {error ? `Odświeżanie nie działa, dane sprzed ${ago}` : `Zaktualizowano ${ago} temu`}
    </p>
  );
}

// Komunikat akcji: {ok, message} albo walidacja compose ({validation, output})
export function Msg({ msg }) {
  if (!msg) return null;
  if (msg.validation) {
    return (<><p className="err">Walidacja nie przeszła, plik NIE został zapisany:</p><pre className="log">{msg.output}</pre></>);
  }
  return <p className={msg.ok ? 'ok-t' : 'err'}>{msg.message}</p>;
}

// Przełącznik zakresu: wybrany przycisk ma aria-pressed="true" (styl w CSS wynika z tego atrybutu)
export function RangeButtons({ ranges, value, onChange, cls = '' }) {
  return ranges.map(r => (
    <button key={r} className={`ghost ${cls}`} aria-pressed={r === value} onClick={() => onChange(r)}>{r}</button>
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
      {agents.map(a => (
        <Link key={a.key} className={`tab ${a.key === current ? 'on' : ''}`}
              aria-current={a.key === current ? 'page' : undefined} to={`?s=${a.key}`}>{a.name}</Link>
      ))}
    </div>
  );
}

export const Loading = ({ error }) => error
  ? <p className="err">Nie udało się pobrać danych: {error}</p>
  : <p className="muted">…</p>;