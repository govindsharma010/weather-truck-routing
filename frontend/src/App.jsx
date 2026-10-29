import { useCallback, useEffect, useRef, useState } from "react";
import CheckpointTable from "./components/CheckpointTable.jsx";
import MapView from "./components/MapView.jsx";
import RouteCards from "./components/RouteCards.jsx";
import TripForm from "./components/TripForm.jsx";
import { planTrip } from "./lib/api.js";

export default function App() {
  const [data, setData] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [focusIndex, setFocusIndex] = useState(null);
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
      const result = await planTrip(payload, ctl.signal);
      setData(result);
      setSelectedId(result.recommended_route_id);
      setFocusIndex(null);
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      if (abortRef.current === ctl) setLoading(false);
    }
  }, []);

  const selected = data?.routes.find((r) => r.id === selectedId);

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
          <>
            {data.meta.notes.map((n) => (
              <div key={n} className="card note">
                {n}
              </div>
            ))}
            <RouteCards
              routes={data.routes}
              selectedId={selectedId}
              onSelect={(id) => {
                setSelectedId(id);
                setFocusIndex(null);
              }}
            />
            {selected && <CheckpointTable route={selected} focusIndex={focusIndex} onFocus={setFocusIndex} />}
            <footer>
              Weather: {data.meta.weather_source}. Times shown in your local time zone. Wind metric: {data.meta.wind_metric}.
            </footer>
          </>
        )}
      </aside>
      <main className="map-wrap">
        <MapView
          data={data}
          selectedId={selectedId}
          onSelect={(id) => {
            setSelectedId(id);
            setFocusIndex(null);
          }}
          focusIndex={focusIndex}
          onFocus={setFocusIndex}
        />
        {!data && !loading && <div className="map-hint">Enter a trip to compare three routes.</div>}
        {loading && <div className="map-hint busy">Finding routes and forecasts…</div>}
      </main>
    </div>
  );
}