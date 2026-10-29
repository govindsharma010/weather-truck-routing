import { useCallback, useEffect, useRef, useState } from "react";
import TripForm from "./components/TripForm.jsx";
import { planTrip } from "./lib/api.js";
import { formatDuration } from "./lib/risk.js";

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const submit = useCallback(async (payload) => {
    abortRef.current?.abort();
    const ctl = new AbortController();
    abortRef.current = ctl;
    setLoading(true);
    setError("");
    try {
      setData(await planTrip(payload, ctl.signal));
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      if (abortRef.current === ctl) setLoading(false);
    }
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <header>
          <h1>Weather-Aware Truck Routing</h1>
          <p>Pick the route with the least dangerous weather at the time your truck actually gets there.</p>
        </header>
        <TripForm onSubmit={submit} loading={loading} />
        {error && (
          <div className="card error" role="alert">
            {error}
          </div>
        )}
        {data && (
          <div className="card">
            <h3>Results (temporary view)</h3>
            {data.routes.map((r) => (
              <p key={r.id}>
                <strong>{r.label}</strong>: {r.distance_mi} mi, {formatDuration(r.duration_s)}, worst risk{" "}
                {r.summary.max_level_label}, severe {r.summary.miles_by_level.severe} mi
                {r.recommended && " ← recommended"}
              </p>
            ))}
          </div>
        )}
      </aside>
      <main className="map-wrap">
        <div className="map-hint">The map comes in a later step.</div>
      </main>
    </div>
  );
}