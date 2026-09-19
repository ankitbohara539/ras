import type { Hazard } from './types'

/** How each kind of hazard is drawn and named. */
export const HAZARD_KINDS: Record<string, { icon: string; label: [string, string] }> = {
  flooding: { icon: '🌊', label: ['Flooded road', 'डुबानमा परेको सडक'] },
  blocked_road: { icon: '🚧', label: ['Blocked road', 'अवरुद्ध सडक'] },
  electrical: { icon: '⚡', label: ['Unsafe electrical area', 'असुरक्षित बिजुली'] },
  dark_street: { icon: '🌑', label: ['Broken streetlight', 'बिग्रिएको सडक बत्ती'] },
  open_drain: { icon: '🕳️', label: ['Open drain / manhole', 'खुला ढल / म्यानहोल'] },
  damaged_footpath: { icon: '🚷', label: ['Damaged footpath', 'बिग्रिएको फुटपाथ'] },
  wheelchair_barrier: { icon: '♿', label: ['Wheelchair barrier', 'ह्वीलचेयर अवरोध'] },
  road_damage: { icon: '🛣️', label: ['Road damage', 'सडक क्षति'] },
  alert_area: { icon: '📢', label: ['Public alert area', 'सार्वजनिक चेतावनी क्षेत्र'] },
}

export function hazardKind(kind: string) {
  return HAZARD_KINDS[kind] ?? { icon: '⚠️', label: ['Hazard', 'खतरा'] as [string, string] }
}

export const SEVERITY_COLOR: Record<Hazard['severity'], string> = {
  high: '#c62828',
  medium: '#e08a00',
  low: '#6d7a8a',
}

export function formatDuration(seconds: number): string {
  const minutes = Math.max(1, Math.round(seconds / 60))
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}
