import { useEffect, useState } from "react";

export default function App() {
  const [status, setStatus] = useState("checking...");

  useEffect(() => {
    fetch("/api/health/")
      .then((r) => r.json())
      .then((d) => setStatus(d.status))
      .catch(() => setStatus("backend not reachable"));
  }, []);

  return (
    <div style={{ padding: 24 }}>
      <h1>Weather-Aware Truck Routing</h1>
      <p>
        Backend status: <strong>{status}</strong>
      </p>
    </div>
  );
}