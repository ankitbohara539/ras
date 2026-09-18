import { useCallback, useState } from 'react'
import type { Coords } from './types'

export type GeoState =
  | { kind: 'idle' }
  | { kind: 'locating' }
  | { kind: 'ready'; coords: Coords; accuracy: number }
  | { kind: 'error'; message: string }

/**
 * Browser geolocation with human-readable failures.
 *
 * The default GeolocationPositionError messages are useless to a citizen
 * ("User denied Geolocation"), and location is mandatory here -- without it
 * the report cannot be routed to a ward.
 */
export function useGeolocation() {
  const [state, setState] = useState<GeoState>({ kind: 'idle' })

  const locate = useCallback(() => {
    if (!('geolocation' in navigator)) {
      setState({
        kind: 'error',
        message: 'This browser cannot share your location.',
      })
      return
    }

    setState({ kind: 'locating' })

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setState({
          kind: 'ready',
          coords: {
            latitude: Number(position.coords.latitude.toFixed(6)),
            longitude: Number(position.coords.longitude.toFixed(6)),
          },
          accuracy: Math.round(position.coords.accuracy),
        })
      },
      (error) => {
        const messages: Record<number, string> = {
          1: 'Location permission was denied. Allow it in your browser settings, then try again.',
          2: 'Your location is unavailable right now. Move to an open area and try again.',
          3: 'Finding your location took too long. Try again.',
        }
        setState({
          kind: 'error',
          message: messages[error.code] ?? 'Could not get your location.',
        })
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 },
    )
  }, [])

  const setManual = useCallback((coords: Coords) => {
    setState({ kind: 'ready', coords, accuracy: 0 })
  }, [])

  return { state, locate, setManual }
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
