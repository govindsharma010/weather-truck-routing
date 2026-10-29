import L from "leaflet";
import { Fragment, memo, useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import { colorFor, formatDateTime } from "../lib/risk.js";

const pin = (text) => L.divIcon({ className: "pin-wrap", html: `<div class="pin">${text}</div>`, iconSize: [28, 28], iconAnchor: [14, 14] });
const ORIGIN_ICON = pin("A");
const DEST_ICON = pin("B");

function FitBounds({ routes }) {
  const map = useMap();
  useEffect(() => {
    if (!routes.length) return;
    const b = L.latLngBounds(routes.flatMap((r) => r.bounds));
    map.fitBounds(b, { padding: [40, 40] });
  }, [routes, map]);
  return null;
}

function PanToFocus({ route, focusIndex }) {
  const map = useMap();
  useEffect(() => {
    const cp = route?.checkpoints[focusIndex];
    if (cp) map.panTo([cp.lat, cp.lon]);
  }, [route, focusIndex, map]);
  return null;
}

/** All route polylines, coloured per risk segment. Memoised so unrelated re-renders never redraw them. */
const RouteLines = memo(function RouteLines({ routes, selectedId, onSelect }) {
  // Draw the selected route last so it sits on top of the others.
  const ordered = useMemo(() => [...routes].sort((a, b) => (a.id === selectedId) - (b.id === selectedId)), [routes, selectedId]);
  return ordered.map((r) => {
    const selected = r.id === selectedId;
    return (
      <Fragment key={r.id}>
        {selected && (
          <Polyline
            positions={r.segments.flatMap((s) => s.geometry)}
            pathOptions={{ color: "#fff", weight: 11, opacity: 0.85, lineCap: "round", interactive: false }}
          />
        )}
        {r.segments.map((s, i) => (
          <Polyline
            key={i}
            positions={s.geometry}
            pathOptions={{
              color: colorFor(s.level),
              weight: selected ? 6 : 4,
              opacity: selected ? 1 : 0.55,
              dashArray: selected ? undefined : "7 9",
              lineCap: "butt",
            }}
            eventHandlers={{ click: () => onSelect(r.id) }}
          />
        ))}
      </Fragment>
    );
  });
});

const Checkpoints = memo(function Checkpoints({ route, focusIndex, onFocus }) {
  const small = route.checkpoints.length > 60;
  return route.checkpoints.map((c) => (
    <CircleMarker
      key={c.index}
      center={[c.lat, c.lon]}
      radius={c.index === focusIndex ? 10 : small ? 4 : 6}
      pathOptions={{ color: c.index === focusIndex ? "#111" : "#fff", weight: c.index === focusIndex ? 3 : 1.5, fillColor: colorFor(c.level), fillOpacity: 1 }}
      eventHandlers={{ click: () => onFocus(c.index) }}
    >
      <Popup>
        <div className="popup">
          <strong>
            Mile {c.mile} · {c.level_label}
          </strong>
          <div>ETA {formatDateTime(c.eta)}</div>
          <div>
            Wind {c.wind_mph} mph · Rain {c.rain_in_hr} in/hr · Snow {c.snow_in_hr} in/hr
          </div>
          {c.drivers.map((d) => (
            <div key={d} className="driver">{d}</div>
          ))}
          {!c.forecast_available && <div className="driver">Beyond forecast range</div>}
        </div>
      </Popup>
    </CircleMarker>
  ));
});

export default function MapView({ data, selectedId, onSelect, focusIndex, onFocus }) {
  const selected = data?.routes.find((r) => r.id === selectedId);
  return (
    <MapContainer center={[39.5, -98.35]} zoom={5} className="map" preferCanvas={false} zoomControl>
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {data && (
        <>
          <FitBounds routes={data.routes} />
          <RouteLines routes={data.routes} selectedId={selectedId} onSelect={onSelect} />
          {selected && <Checkpoints route={selected} focusIndex={focusIndex} onFocus={onFocus} />}
          {selected && <PanToFocus route={selected} focusIndex={focusIndex} />}
          <Marker position={[data.meta.origin.lat, data.meta.origin.lon]} icon={ORIGIN_ICON} />
          <Marker position={[data.meta.destination.lat, data.meta.destination.lon]} icon={DEST_ICON} />
        </>
      )}
    </MapContainer>
  );
}