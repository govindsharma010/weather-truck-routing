import { colorFor, formatDateTime } from "../lib/risk.js";

export default function CheckpointTable({ route, focusIndex, onFocus }) {
  return (
    <div className="card table-card">
      <h3>{route.label} checkpoints</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA</th>
              <th>Risk</th>
              <th>Wind</th>
              <th>Rain</th>
              <th>Snow</th>
            </tr>
          </thead>
          <tbody>
            {route.checkpoints.map((c) => (
              <tr key={c.index} className={c.index === focusIndex ? "focus" : ""} onClick={() => onFocus(c.index)} title={c.drivers.join("\n")}>
                <td>{c.mile}</td>
                <td>{formatDateTime(c.eta, { weekday: undefined })}</td>
                <td>
                  <span className="pill" style={{ background: colorFor(c.level) }}>
                    {c.level_label}
                  </span>
                  {c.load_adjusted && <span className="load-flag" title="Raised because of your load weight"> ⚖</span>}
                </td>
                <td>{c.wind_mph} mph</td>
                <td>{c.rain_in_hr} in/h</td>
                <td>{c.snow_in_hr} in/h</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}