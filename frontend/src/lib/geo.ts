import { useCallback, useEffect, useRef, useState } from 'react'
import type { Coords } from './types'

export type GeoState =
  | { kind: 'idle' }
  | { kind: 'locating' }
  | {
      kind: 'ready'
      coords: Coords
      /** Metres, 95% radius as the device reports it. 0 when set by hand. */
      accuracy: number
      /** 'manual' once the citizen has placed the pin themselves. */
      source: 'gps' | 'manual'
      /** Still listening for a better fix. */
      refining: boolean
    }
  | { kind: 'error'; message: string }

// Stop listening once a fix is this good, or after this long regardless.
const GOOD_ENOUGH_M = 20
const SAMPLE_FOR_MS = 12000

/** Coordinates at 6 decimals: ~11cm, finer than any phone GPS. */
export function roundCoords(latitude: number, longitude: number): Coords {
  return {
    latitude: Number(latitude.toFixed(6)),
    longitude: Number(longitude.toFixed(6)),
  }
}

/**
 * Browser geolocation with human-readable failures.
 *
 * The first fix a device returns is often its coarse Wi-Fi or cell-tower
 * guess -- hundreds of metres, sometimes kilometres off -- with real GPS
 * arriving seconds later. So instead of taking the first answer, this keeps
 * listening for a few seconds and keeps the most accurate one. And it never
 * accepts a cached position: that is wherever the phone was last time.
 *
 * The default GeolocationPositionError messages are useless to a citizen
 * ("User denied Geolocation"), and location is mandatory here -- without it
 * the report cannot be routed to a ward.
 */
export function useGeolocation({ refine = true }: { refine?: boolean } = {}) {
  const [state, setState] = useState<GeoState>({ kind: 'idle' })
  const watchRef = useRef<number | null>(null)
  const timerRef = useRef<number | null>(null)

  const stopWatching = useCallback(() => {
    if (watchRef.current !== null) {
      navigator.geolocation.clearWatch(watchRef.current)
      watchRef.current = null
    }
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => stopWatching, [stopWatching])

  const locate = useCallback(() => {
    if (!('geolocation' in navigator)) {
      setState({
        kind: 'error',
        message: 'This browser cannot share your location.',
      })
      return
    }

    stopWatching()
    setState({ kind: 'locating' })

    const errorMessages: Record<number, string> = {
      1: 'Location permission was denied. Allow it in your browser settings, then try again.',
      2: 'Your location is unavailable right now. Move to an open area and try again.',
      3: 'Finding your location took too long. Try again, or place the pin on the map.',
    }

    // Lists sorted by distance only need a rough position, and every
    // improved fix would reload them -- the spinner flashing three times.
    // One answer, a recent cached one is fine.
    if (!refine) {
      navigator.geolocation.getCurrentPosition(
        (position) =>
          setState({
            kind: 'ready',
            coords: roundCoords(position.coords.latitude, position.coords.longitude),
            accuracy: Math.round(position.coords.accuracy),
            source: 'gps',
            refining: false,
          }),
        (error) =>
          setState({
            kind: 'error',
            message: errorMessages[error.code] ?? 'Could not get your location.',
          }),
        { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 },
      )
      return
    }

    let best: GeolocationPosition | null = null

    const finish = () => {
      stopWatching()
      setState((current) =>
        current.kind === 'ready' ? { ...current, refining: false } : current,
      )
    }

    watchRef.current = navigator.geolocation.watchPosition(
      (position) => {
        if (best && position.coords.accuracy >= best.coords.accuracy) return
        best = position

        const goodEnough = position.coords.accuracy <= GOOD_ENOUGH_M
        setState({
          kind: 'ready',
          coords: roundCoords(position.coords.latitude, position.coords.longitude),
          accuracy: Math.round(position.coords.accuracy),
          source: 'gps',
          refining: !goodEnough,
        })
        if (goodEnough) finish()
      },
      (error) => {
        // A timeout after we already have a fix is fine: keep the fix.
        if (best) {
          finish()
          return
        }
        stopWatching()
        setState({
          kind: 'error',
          message: errorMessages[error.code] ?? 'Could not get your location.',
        })
      },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
    )

    timerRef.current = window.setTimeout(finish, SAMPLE_FOR_MS)
  }, [stopWatching, refine])

  /** The citizen put the pin where the problem is. That beats any GPS. */
  const setManual = useCallback(
    (coords: Coords) => {
      stopWatching()
      setState({
        kind: 'ready',
        coords: roundCoords(coords.latitude, coords.longitude),
        accuracy: 0,
        source: 'manual',
        refining: false,
      })
    },
    [stopWatching],
  )

  return { state, locate, setManual }
}

export function formatCoords(latitude: number, longitude: number): string {
  const ns = latitude >= 0 ? 'N' : 'S'
  const ew = longitude >= 0 ? 'E' : 'W'
  return `${Math.abs(latitude).toFixed(6)}° ${ns}, ${Math.abs(longitude).toFixed(6)}° ${ew}`
}

export function mapsLink(latitude: number, longitude: number): string {
  return `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`
}

export function formatDistance(metres: number | null | undefined): string {
  if (metres === null || metres === undefined) return ''
  if (metres < 1000) return `${Math.round(metres)}m`
  return `${(metres / 1000).toFixed(1)}km`
}

export function formatDate(iso: string, language: 'en' | 'ne' = 'en'): string {
  const date = new Date(iso)
  return new Intl.DateTimeFormat(language === 'ne' ? 'ne-NP' : 'en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function relativeTime(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)

  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}
