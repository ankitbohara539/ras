"use client";

import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Crosshair, Layers3, MapPin, Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useReadingPreferences } from "@/features/preferences/reading-preferences";
import { api } from "@/lib/api/client";
import type { Issue, Page } from "@/types";
import type { MapMarker } from "./LeafletMap";

const LeafletMap = dynamic(() => import("./LeafletMap"), { ssr: false });

type GeocodeResult = {
  display_name: string;
  latitude: number;
  longitude: number;
  ward: string | null;
  source: string;
};

export function MapCard() {
  const [center, setCenter] = useState<[number, number]>([27.7172, 85.324]);
  const [query, setQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [accuracy, setAccuracy] = useState<number | null>(null);
  const [selectedPlace, setSelectedPlace] = useState<GeocodeResult | null>(null);
  const { preferences } = useReadingPreferences();
  const issues = useQuery({
    queryKey: ["issues", "nearby", ...center],
    queryFn: () => api<Page<Issue>>("/issues/nearby?lat=" + center[0] + "&lng=" + center[1] + "&radius=5000&page_size=100"),
  });
  const search = useQuery({
    queryKey: ["geo-search", searchTerm, preferences.language],
    queryFn: () => api<GeocodeResult[]>("/geo/search?q=" + encodeURIComponent(searchTerm + ", Kathmandu") + "&limit=5&language=" + preferences.language),
    enabled: searchTerm.length >= 3,
    retry: false,
  });
  const markers: MapMarker[] = (issues.data?.items ?? [])
    .filter((item) => item.latitude != null && item.longitude != null)
    .map((item) => ({
      id: item.id,
      latitude: item.latitude as number,
      longitude: item.longitude as number,
      title: item.title,
      kind: "issue",
    }));
  const locate = () => navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      setCenter([coords.latitude, coords.longitude]);
      setAccuracy(Math.round(coords.accuracy));
      setSelectedPlace(null);
    },
    () => toast.error("We could not access your location. Search for a Kathmandu landmark instead."),
    { enableHighAccuracy: true, timeout: 12_000, maximumAge: 15_000 },
  );
  return (
    <section className="map-card">
      <div className="map-toolbar"><div><Layers3 size={18} /><span>{markers.length} nearby reports · Kathmandu Metro</span></div><button className="button secondary" onClick={locate}><Crosshair size={17} /> Center on me</button></div>
      <form className="map-search" onSubmit={(event) => { event.preventDefault(); setSearchTerm(query.trim()); }}>
        <label><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search a place or landmark in Kathmandu" aria-label="Search Kathmandu map" /></label>
        <button className="button primary" disabled={query.trim().length < 3 || search.isFetching}>Search map</button>
      </form>
      {search.data?.length ? <div className="map-search-results">{search.data.map((place) => <button type="button" key={place.display_name} onClick={() => { setCenter([place.latitude, place.longitude]); setSelectedPlace(place); setAccuracy(null); }}><MapPin size={15} /><span>{place.display_name}<small>{place.ward ?? "Kathmandu Metropolitan City"}</small></span></button>)}</div> : null}
      {search.isError ? <p className="map-search-empty" role="alert">Address search is temporarily unavailable. You can still use your device location.</p> : null}
      {searchTerm && !search.isFetching && !search.isError && !search.data?.length ? <p className="map-search-empty">No matching place found inside the Kathmandu search area.</p> : null}
      <LeafletMap center={center} markers={markers} />
      <div className="map-caption"><span>{selectedPlace ? selectedPlace.display_name : accuracy ? `Device location · accuracy about ${accuracy} m` : "Centered on Kathmandu Metropolitan City"}</span><span>Search © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a> · Nominatim</span></div>
    </section>
  );
}
