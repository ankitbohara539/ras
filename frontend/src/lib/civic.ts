import type { CivicCategory, CivicStatus } from './types'

/** The four groups the citizen picks from, each with its specific acts. */
export const CIVIC_GROUPS: { key: string; icon: string; categories: CivicCategory[] }[] = [
  { key: 'waste', icon: '🗑️', categories: ['littering', 'dumping_waste', 'burning_waste'] },
  {
    key: 'nuisance',
    icon: '🚯',
    categories: ['spitting', 'public_urination', 'smoking_in_public', 'noise'],
  },
  { key: 'obstruction', icon: '🚗', categories: ['illegal_parking', 'footpath_encroachment'] },
  { key: 'damage', icon: '🧱', categories: ['vandalism', 'pet_waste', 'other'] },
]

export const CIVIC_STATUSES: CivicStatus[] = [
  'submitted',
  'under_review',
  'action_taken',
  'dismissed',
]

/** Where an office can move a complaint next -- mirrors the API's rules. */
export const CIVIC_NEXT: Record<CivicStatus, CivicStatus[]> = {
  submitted: ['under_review', 'action_taken', 'dismissed'],
  under_review: ['action_taken', 'dismissed'],
  action_taken: ['under_review'],
  dismissed: ['under_review'],
}

/** Closing needs a note: the reporter is told what happened. */
export const CIVIC_NEEDS_NOTE: CivicStatus[] = ['action_taken', 'dismissed']
