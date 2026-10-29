// Single source of truth for risk colours/labels on the client. Colour is never the only signal:
// every place that uses one also prints the level name.
export const LEVELS = [
  { key: "low", label: "Low", color: "#2f9e62" },
  { key: "moderate", label: "Moderate", color: "#d9a90c" },
  { key: "high", label: "High", color: "#ee8a1f" },
  { key: "severe", label: "Severe", color: "#d63b2f" },
  { key: "no_travel", label: "No Travel", color: "#6d28a8" },
];

export const LEVEL_BY_KEY = Object.fromEntries(LEVELS.map((l) => [l.key, l]));

export const colorFor = (key) => LEVEL_BY_KEY[key]?.color ?? "#888";

export function formatDuration(seconds) {
  const m = Math.round(seconds / 60);
  const h = Math.floor(m / 60);
  return h ? `${h}h ${String(m % 60).padStart(2, "0")}m` : `${m}m`;
}

export const formatMiles = (mi) => `${Math.round(mi).toLocaleString()} mi`;

export function formatDateTime(iso, opts = {}) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    ...opts,
  });
}