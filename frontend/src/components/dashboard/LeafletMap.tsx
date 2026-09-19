"use client";

import { useEffect } from "react";
import { CircleMarker, MapContainer, Popup, ScaleControl, TileLayer, useMap } from "react-leaflet";

export type MapMarker = {
  id: string;
  latitude: number;
  longitude: number;
  title: string;
  kind: "issue" | "service" | "emergency";
};

function RecenterMap({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, Math.max(map.getZoom(), 15), { duration: 0.8 });
  }, [center, map]);
  return null;
}

export default function LeafletMap({
  center,
  markers,
}: {
  center: [number, number];
  markers: MapMarker[];
}) {
  const tileUrl = process.env.NEXT_PUBLIC_MAP_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const attribution = process.env.NEXT_PUBLIC_MAP_ATTRIBUTION ?? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>';
  return (
    <MapContainer
      center={center}
      zoom={14}
      minZoom={11}
      maxZoom={19}
      maxBounds={[[27.61, 85.20], [27.82, 85.45]]}
      maxBoundsViscosity={0.75}
      scrollWheelZoom
      className="leaflet-map"
    >
      <RecenterMap center={center} />
      <TileLayer url={tileUrl} attribution={attribution} />
      <ScaleControl imperial={false} />
      {markers.map((marker) => (
        <CircleMarker
          key={marker.id}
          center={[marker.latitude, marker.longitude]}
          radius={9}
          pathOptions={{ color: marker.kind === "emergency" ? "#c63f36" : marker.kind === "service" ? "#2866a9" : "#0b846d", fillOpacity: 0.85 }}
        >
          <Popup><strong>{marker.title}</strong><br />{marker.kind}</Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
