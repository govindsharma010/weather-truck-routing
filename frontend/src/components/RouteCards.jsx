import { LEVELS, colorFor, formatDateTime, formatDuration, formatMiles } from "../lib/risk.js";

function RiskBar({ miles, total }) {
  return (
    <div className="riskbar" role="img" aria-label="Miles by risk level">
      {LEVELS.map((l) => {
        const m = miles[l.key] ?? 0;
        return m > 0 ? <span key={l.key} style={{ width: `${(m / total) * 100}%`, background: l.color }} title={`${l.label}: ${Math.round(m)} mi`} /> : null;
      })}
    </div>
  );
}

export default function RouteCards({ routes, selectedId, onSelect }) {
  const ordered = [...routes].sort((a, b) => a.rank - b.rank);
  return (
    <div className="routes" role="radiogroup" aria-label="Route options">
      {ordered.map((r) => {
        const s = r.summary;
        const m = s.miles_by_level;
        return (
          <button
            key={r.id}
            role="radio"
            aria-checked={r.id === selectedId}
            className={`card route ${r.id === selectedId ? "selected" : ""}`}
            onClick={() => onSelect(r.id)}
          >
            <div className="route-head">
              <strong>{r.label}</strong>
              {r.recommended && <span className="badge good">Recommended</span>}
              {r.fastest && <span className="badge">Fastest</span>}
              <span className="badge" style={{ background: colorFor(LEVELS[s.max_level].key), color: "#fff" }}>
                Worst: {s.max_level_label}
              </span>
            </div>
            <div className="route-stats">
              <span>{formatMiles(r.distance_mi)}</span>
              <span>{formatDuration(r.duration_s)}</span>
              <span>Arrive {formatDateTime(r.arrival)}</span>
            </div>
            <RiskBar miles={m} total={r.distance_mi} />
            <div className="route-miles">
              <span>Severe {Math.round(m.severe)} mi</span>
              <span>High {Math.round(m.high)} mi</span>
              {m.no_travel > 0 && <span className="danger">No Travel {Math.round(m.no_travel)} mi</span>}
              <span>Avg risk {s.avg_risk.toFixed(2)}/4</span>
            </div>
            {r.recommended && r.explanation && <p className="why">{r.explanation}</p>}
          </button>
        );
      })}
    </div>
  );
}