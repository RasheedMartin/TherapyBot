import { useEffect, useMemo } from "react";
import { Box, Typography, useTheme } from "@mui/material";
import L from "leaflet";
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { Provider } from "../../api/types";

interface ProviderMapProps {
  providers: Provider[];
  center: { lat: number; lng: number } | null;
  selected: string | null;
  saved: Set<string>;
  userLocation: { lat: number; lng: number } | null;
  onSelect: (npi: string) => void;
}

const US_CENTER: [number, number] = [39.8, -98.6];

/** A map pin; when several providers share an address it shows how many. */
const pinIcon = (color: string, size: number, ring: boolean, count = 1) =>
  L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size],
    html: `<svg width="${size}" height="${size}" viewBox="0 0 24 24" style="filter: drop-shadow(0 1px 2px rgba(0,0,0,.35))">
      <path fill="${color}" stroke="${ring ? "#fff" : "rgba(255,255,255,.85)"}" stroke-width="${ring ? 2 : 1.25}"
        d="M12 2C8 2 5 5 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-4-3-7-7-7z"/>
      ${
        count > 1
          ? `<text x="12" y="11.6" text-anchor="middle" font-size="${count > 9 ? 6.5 : 8}" font-weight="700" font-family="system-ui, sans-serif" fill="#fff">${count}</text>`
          : `<circle cx="12" cy="9" r="2.6" fill="#fff"/>`
      }</svg>`,
  });

interface PinGroup {
  key: string;
  lat: number;
  lng: number;
  providers: Provider[];
}

const groupByLocation = (providers: Provider[]): PinGroup[] => {
  const groups = new Map<string, PinGroup>();
  for (const p of providers) {
    if (p.lat == null || p.lng == null) continue;
    const key = `${p.lat.toFixed(5)},${p.lng.toFixed(5)}`;
    const group = groups.get(key) ?? { key, lat: p.lat, lng: p.lng, providers: [] };
    group.providers.push(p);
    groups.set(key, group);
  }
  return [...groups.values()];
};

/** Keeps the map framed: fit all pins on new results, fly to a pin when one is selected. */
const MapController = ({ providers, selected, center }: Pick<ProviderMapProps, "providers" | "selected" | "center">) => {
  const map = useMap();
  const pinned = useMemo(() => providers.filter((p) => p.lat != null && p.lng != null), [providers]);

  useEffect(() => {
    if (pinned.length > 1) {
      map.fitBounds(L.latLngBounds(pinned.map((p) => [p.lat!, p.lng!])), { padding: [40, 40], maxZoom: 14 });
    } else if (center) {
      map.setView([center.lat, center.lng], 13);
    }
  }, [map, pinned, center]);

  useEffect(() => {
    const target = pinned.find((p) => p.npi === selected);
    if (target) map.flyTo([target.lat!, target.lng!], Math.max(map.getZoom(), 15), { duration: 0.6 });
  }, [map, pinned, selected]);

  return null;
};

export const ProviderMap = ({ providers, center, selected, saved, userLocation, onSelect }: ProviderMapProps) => {
  const theme = useTheme();
  const groups = useMemo(() => groupByLocation(providers), [providers]);
  const iconFor = (group: PinGroup) => {
    const count = group.providers.length;
    if (group.providers.some((p) => p.npi === selected)) return pinIcon(theme.palette.error.main, 40, true, count);
    if (group.providers.some((p) => saved.has(p.npi))) return pinIcon(theme.palette.secondary.main, 32, false, count);
    return pinIcon(theme.palette.primary.main, count > 1 ? 32 : 28, false, count);
  };

  return (
    <Box sx={{ height: "100%", width: "100%", "& .leaflet-container": { height: "100%", width: "100%", fontFamily: "inherit" } }}>
      <MapContainer center={center ? [center.lat, center.lng] : US_CENTER} zoom={center ? 13 : 4} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapController providers={providers} selected={selected} center={center} />
        {groups.map((group) => (
          <Marker
            key={group.key}
            position={[group.lat, group.lng]}
            icon={iconFor(group)}
            zIndexOffset={group.providers.some((p) => p.npi === selected) ? 1000 : group.providers.length}
            eventHandlers={{ click: () => group.providers.length === 1 && onSelect(group.providers[0].npi) }}
          >
            <Popup>
              {group.providers.length > 1 && (
                <Typography variant="caption" color="text.secondary" component="div" mb={0.5}>
                  {group.providers.length} providers at {group.providers[0].street}
                </Typography>
              )}
              <Box sx={{ maxHeight: 220, overflowY: "auto", minWidth: 200 }}>
                {group.providers.map((p) => (
                  <Box
                    key={p.npi}
                    onClick={() => onSelect(p.npi)}
                    sx={{
                      py: 0.5,
                      cursor: group.providers.length > 1 ? "pointer" : "default",
                      borderRadius: 1,
                      "&:hover": group.providers.length > 1 ? { bgcolor: "action.hover" } : {},
                    }}
                  >
                    <Typography variant="subtitle2" component="div" color={p.npi === selected ? "error" : "inherit"}>
                      {p.name}
                      {p.credential && `, ${p.credential}`}
                    </Typography>
                    <Typography variant="caption" component="div" color="text.secondary">
                      {p.specialty}
                      {p.phone && " · "}
                      {p.phone && <a href={`tel:${p.phone}`}>{p.phone}</a>}
                    </Typography>
                  </Box>
                ))}
              </Box>
              {group.providers.length === 1 && (
                <Typography variant="caption" component="div">
                  {group.providers[0].street}, {group.providers[0].city}
                </Typography>
              )}
            </Popup>
          </Marker>
        ))}
        {userLocation && (
          <CircleMarker
            center={[userLocation.lat, userLocation.lng]}
            radius={8}
            pathOptions={{ color: "#fff", weight: 3, fillColor: "#1a73e8", fillOpacity: 1 }}
          >
            <Popup>You are here</Popup>
          </CircleMarker>
        )}
      </MapContainer>
    </Box>
  );
};
