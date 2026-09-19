import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { hazardKind, SEVERITY_COLOR } from '../lib/hazards'
import type { Coords, Hazard, RoutePlan } from '../lib/types'

type Box = { min_lat: number; min_lon: number; max_lat: number; max_lon: number }

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}

function endpointIcon(label: string, color: string) {
  return L.divIcon({
    className: 'map-endpoint',
    html: `<span style="background:${color}">${label}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })
}

/**
 * The hazard map: hazard zones as circles, the planned routes as lines, and
 * the start and destination. Tapping the map reports a point (the page
 * decides whether it is the start or the destination).
 *
 * Built on Leaflet directly, like LocationMap: layers are redrawn in place
 * when data changes, and the map itself is created once.
 */
export function HazardMap({
  center,
  hazards,
  plan,
  start,
  end,
  language,
  onPick,
  onView,
}: {
  center: Coords
  hazards: Hazard[]
  plan: RoutePlan | null
  start: Coords | null
  end: Coords | null
  language: 'en' | 'ne'
  onPick: (coords: Coords) => void
  onView: (box: Box) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const hazardLayer = useRef<L.LayerGroup | null>(null)
  const routeLayer = useRef<L.LayerGroup | null>(null)
  const pointLayer = useRef<L.LayerGroup | null>(null)
  const onPickRef = useRef(onPick)
  const onViewRef = useRef(onView)
  onPickRef.current = onPick
  onViewRef.current = onView

  useEffect(() => {
    if (!containerRef.current) return
    const map = L.map(containerRef.current, {
      center: [center.latitude, center.longitude],
      zoom: 15,
    })
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map)

    hazardLayer.current = L.layerGroup().addTo(map)
    routeLayer.current = L.layerGroup().addTo(map)
    pointLayer.current = L.layerGroup().addTo(map)

    const report = () => {
      const b = map.getBounds()
      onViewRef.current({
        min_lat: b.getSouth(),
        min_lon: b.getWest(),
        max_lat: b.getNorth(),
        max_lon: b.getEast(),
      })
    }
    map.on('moveend', report)
    map.on('click', (event: L.LeafletMouseEvent) => {
      const p = event.latlng.wrap()
      onPickRef.current({ latitude: p.lat, longitude: p.lng })
    })

    mapRef.current = map
    const timer = window.setTimeout(() => {
      map.invalidateSize()
      report()
    }, 150)

    return () => {
      window.clearTimeout(timer)
      map.remove()
      mapRef.current = null
    }
    // Created once; center is only the initial view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Hazard zones.
  useEffect(() => {
    const layer = hazardLayer.current
    if (!layer) return
    layer.clearLayers()
    const onRoute = new Set([
      ...(plan?.fastest.hazard_ids ?? []),
      ...(plan?.safer?.hazard_ids ?? []),
    ])

    for (const hazard of hazards) {
      const meta = hazardKind(hazard.kind)
      const color = SEVERITY_COLOR[hazard.severity]
      const dimmed = !hazard.active_now
      L.circle([hazard.latitude, hazard.longitude], {
        radius: hazard.radius_m,
        color,
        weight: onRoute.has(hazard.id) ? 3 : 1,
        dashArray: hazard.approximate || dimmed ? '6 6' : undefined,
        fillOpacity: dimmed ? 0.05 : 0.18,
        opacity: dimmed ? 0.5 : 0.9,
      }).addTo(layer)

      const label = language === 'ne' ? meta.label[1] : meta.label[0]
      const details = [
        `<strong>${meta.icon} ${escapeHtml(label)}</strong>`,
        escapeHtml(hazard.title),
        hazard.source === 'ticket'
          ? `${hazard.reports} report(s)${hazard.confirmations ? `, ${hazard.confirmations} confirmed` : ''}`
          : 'Public alert',
        hazard.night_only ? (hazard.active_now ? 'Hazard after dark (now)' : 'Only after dark') : '',
        hazard.approximate ? 'Approximate area (whole ward)' : '',
        hazard.ticket_id ? `<a href="/tickets/${hazard.ticket_id}">Open report →</a>` : '',
      ].filter(Boolean)

      L.marker([hazard.latitude, hazard.longitude], {
        icon: L.divIcon({
          className: 'hazard-icon',
          html: `<span style="border-color:${color};opacity:${dimmed ? 0.55 : 1}">${meta.icon}</span>`,
          iconSize: [28, 28],
          iconAnchor: [14, 14],
        }),
        keyboard: true,
        title: label,
      })
        .bindPopup(details.join('<br/>'))
        .addTo(layer)
    }
  }, [hazards, plan, language])

  // Routes: the usual one grey and dashed, the suggested one bold green.
  useEffect(() => {
    const layer = routeLayer.current
    const map = mapRef.current
    if (!layer || !map) return
    layer.clearLayers()
    if (!plan) return

    const fastestRecommended = plan.recommended === 'fastest'
    const fastest = L.polyline(plan.fastest.line, {
      color: fastestRecommended ? '#1b7f3b' : '#6d7a8a',
      weight: fastestRecommended ? 6 : 4,
      dashArray: fastestRecommended ? undefined : '8 8',
      opacity: 0.9,
    }).addTo(layer)

    let bounds = fastest.getBounds()
    if (plan.safer) {
      const safer = L.polyline(plan.safer.line, {
        color: '#1b7f3b',
        weight: 6,
        opacity: 0.95,
      }).addTo(layer)
      bounds = bounds.extend(safer.getBounds())
    }
    map.fitBounds(bounds, { padding: [30, 30] })
  }, [plan])

  // Start and destination.
  useEffect(() => {
    const layer = pointLayer.current
    if (!layer) return
    layer.clearLayers()
    if (start) {
      L.marker([start.latitude, start.longitude], { icon: endpointIcon('A', '#0d5c63') }).addTo(layer)
    }
    if (end) {
      L.marker([end.latitude, end.longitude], { icon: endpointIcon('B', '#c62828') }).addTo(layer)
    }
  }, [start, end])

  return (
    <div
      ref={containerRef}
      className="w-full overflow-hidden rounded-lg"
      style={{ height: '60vh', minHeight: 360, border: '1px solid var(--color-line)', isolation: 'isolate' }}
      role="application"
      aria-label="Hazard map. Tap to choose a destination."
    />
  )
}
