async function request(path, options) {
  let resp;
  try {
    resp = await fetch(path, options);
  } catch {
    throw new Error("Could not reach the server. Check your connection and try again.");
  }
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const fields = body.fields ? Object.entries(body.fields).map(([k, v]) => `${k}: ${[].concat(v).join(" ")}`).join("; ") : "";
    throw new Error(body.error ? (fields ? `${body.error} ${fields}` : body.error) : `Request failed (${resp.status})`);
  }
  return body;
}

export const searchPlaces = (q, signal) =>
  request(`/api/geocode/?q=${encodeURIComponent(q)}`, { signal }).then((r) => r.results);

export const planTrip = (payload, signal) =>
  request("/api/plan/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });