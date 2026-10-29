import { useState } from "react";
import LocationInput from "./LocationInput.jsx";

const pad = (n) => String(n).padStart(2, "0");
const toLocalInput = (d) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

function defaultDeparture() {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  d.setMinutes(0, 0, 0);
  return toLocalInput(d);
}

export default function TripForm({ onSubmit, loading }) {
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [departure, setDeparture] = useState(defaultDeparture);
  const [loadLb, setLoadLb] = useState(42000);
  const [interval, setInterval_] = useState(25);

  // A place is sent as coordinates when picked from the list, otherwise as text for the server to resolve.
  const place = (p) => (p?.lat !== undefined ? { lat: p.lat, lon: p.lon, label: p.label } : p?.label?.trim());

  const submit = (e) => {
    e.preventDefault();
    onSubmit({
      origin: place(origin),
      destination: place(destination),
      departure: new Date(departure).toISOString(),
      load_lb: Number(loadLb),
      checkpoint_interval_mi: Number(interval),
    });
  };

  return (
    <form className="card form" onSubmit={submit}>
      <LocationInput label="Origin" value={origin} onChange={setOrigin} placeholder="e.g. Chicago, IL" />
      <LocationInput label="Destination" value={destination} onChange={setDestination} placeholder="e.g. Denver, CO" />
      <div className="row">
        <label className="field">
          <span>Departure</span>
          <input type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
        </label>
        <label className="field narrow">
          <span>Load (lb)</span>
          <input
            type="number"
            min="1"
            max="150000"
            step="500"
            value={loadLb}
            onChange={(e) => setLoadLb(e.target.value)}
            required
          />
        </label>
      </div>
      <fieldset className="field">
        <legend>Weather checkpoint every</legend>
        <div className="segmented">
          {[10, 25, 50].map((mi) => (
            <label key={mi} className={Number(interval) === mi ? "on" : ""}>
              <input type="radio" name="interval" value={mi} checked={Number(interval) === mi} onChange={() => setInterval_(mi)} />
              {mi} mi
            </label>
          ))}
        </div>
      </fieldset>
      <button className="primary" type="submit" disabled={loading}>
        {loading ? "Checking weather along 3 routes…" : "Find safest route"}
      </button>
    </form>
  );
}