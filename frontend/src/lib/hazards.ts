import type { Hazard } from './types'
import {
  Accessibility,
  AlertTriangle,
  Construction,
  LightbulbOff,
  Megaphone,
  RouteOff,
  Waves,
  Zap,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

type HazardKindMeta = {
  icon: LucideIcon
  marker: string
  label: [string, string]
}

/** How each kind of hazard is drawn and named on the map and in the legend. */
export const HAZARD_KINDS: Record<string, HazardKindMeta> = {
  flooding: { icon: Waves, marker: '≋', label: ['Flooded road', 'डुबानमा परेको सडक'] },
  blocked_road: { icon: Construction, marker: '×', label: ['Blocked road', 'अवरुद्ध सडक'] },
  electrical: { icon: Zap, marker: 'ϟ', label: ['Unsafe electrical area', 'असुरक्षित बिजुली'] },
  dark_street: { icon: LightbulbOff, marker: '◐', label: ['Broken streetlight', 'बिग्रिएको सडक बत्ती'] },
  open_drain: { icon: AlertTriangle, marker: '○', label: ['Open drain / manhole', 'खुला ढल / म्यानहोल'] },
  damaged_footpath: { icon: RouteOff, marker: '↯', label: ['Damaged footpath', 'बिग्रिएको फुटपाथ'] },
  wheelchair_barrier: { icon: Accessibility, marker: '♿', label: ['Wheelchair barrier', 'ह्वीलचेयर अवरोध'] },
  road_damage: { icon: Construction, marker: '⌁', label: ['Road damage', 'सडक क्षति'] },
  alert_area: { icon: Megaphone, marker: '!', label: ['Public alert area', 'सार्वजनिक चेतावनी क्षेत्र'] },
}

export function hazardKind(kind: string) {
  return HAZARD_KINDS[kind] ?? {
    icon: AlertTriangle,
    marker: '!',
    label: ['Hazard', 'खतरा'] as [string, string],
  }
}

export const SEVERITY_COLOR: Record<Hazard['severity'], string> = {
  high: '#c62828',
  medium: '#e08a00',
  low: '#1D293D',
}

export function formatDuration(seconds: number): string {
  const minutes = Math.max(1, Math.round(seconds / 60))
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}
