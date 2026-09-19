import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Coords } from '../lib/types'

/**
 * A small OpenStreetMap view with one pin.
 *
 * Editable on the report form: GPS drops the pin, and the citizen drags it
 * (or taps the map) to where the problem actually is. A phone indoors, or a
 * laptop locating by Wi-Fi, can be hundreds of metres off, and a pothole
 * report that points at the wrong street is worse than no report.
 *
 * Read-only on a ticket, so an officer can see the exact spot.
 */

// A plain CSS pin rather than Leaflet's default PNG marker, which bundlers
// lose track of (the classic "broken image instead of a marker" bug).
const pinIcon = L.divIcon({
  className: 'map-pin',
  html: '<span class="map-pin__head"></span>',
  iconSize: [28, 28],
  // The rotated square's point reaches ~6px below its box.
  iconAnchor: [14, 34],
})

export function LocationMap({
  coords,
  accuracy = 0,
  onChange,
  height = 240,
}: {
  coords: Coords
  /** Metres. Drawn as a circle so the citizen can see how unsure GPS is. */
  accuracy?: number
  /** Present = the pin can be moved. */
  onChange?: (coords: Coords) => void
  height?: number
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markerRef = useRef<L.Marker | null>(null)
  const circleRef = useRef<L.Circle | null>(null)
  // The latest callback, without re-creating the map when the parent re-renders.
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange
  const editable = Boolean(onChange)

  // Build the map once.
  useEffect(() => {
    if (!containerRef.current) return

    const map = L.map(containerRef.current, {
      center: [coords.latitude, coords.longitude],
      zoom: 17,
      scrollWheelZoom: false,
    })
    // No {s} subdomains: OSM asks clients to use the single hostname now.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map)

    const marker = L.marker([coords.latitude, coords.longitude], {
      icon: pinIcon,
      draggable: editable,
      keyboard: editable,
      title: editable ? 'Drag to the exact spot' : undefined,
    }).addTo(map)

    const circle = L.circle([coords.latitude, coords.longitude], {
      radius: accuracy,
      color: '#087F75',
      weight: 1,
      fillOpacity: 0.08,
      interactive: false,
    }).addTo(map)

    if (editable) {
      const move = (latlng: L.LatLng) => {
        const wrapped = latlng.wrap()
        onChangeRef.current?.({ latitude: wrapped.lat, longitude: wrapped.lng })
      }
      marker.on('dragend', () => move(marker.getLatLng()))
      map.on('click', (event: L.LeafletMouseEvent) => move(event.latlng))
    }

    mapRef.current = map
    markerRef.current = marker
    circleRef.current = circle

    // The container can be laid out after the map is created (cards
    // animating in), which leaves grey tiles until the next resize.
    const resize = window.setTimeout(() => map.invalidateSize(), 150)

    return () => {
      window.clearTimeout(resize)
      map.remove()
      mapRef.current = null
      markerRef.current = null
      circleRef.current = null
    }
    // Only on mount: position updates are handled below without a rebuild.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editable])

  // Follow new coordinates (a better GPS fix, or the pin being dragged).
  useEffect(() => {
    const map = mapRef.current
    const marker = markerRef.current
    const circle = circleRef.current
    if (!map || !marker || !circle) return

    const latlng = L.latLng(coords.latitude, coords.longitude)
    marker.setLatLng(latlng)
    circle.setLatLng(latlng)
    circle.setRadius(accuracy)

    if (!map.getBounds().pad(-0.2).contains(latlng)) {
      map.panTo(latlng)
    }
  }, [coords.latitude, coords.longitude, accuracy])

  return (
    <div
      ref={containerRef}
      className="w-full overflow-hidden rounded-lg"
      // Leaflet's panes sit at z-index 400+; isolate them so the map does
      // not scroll over the sticky header.
      style={{ height, border: '1px solid var(--color-line)', isolation: 'isolate' }}
      role="application"
      aria-label={editable ? 'Map: drag the pin to the exact location' : 'Map of the location'}
    />
  )
}
