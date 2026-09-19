export type UserRole = 'citizen' | 'authority' | 'admin'
export type AccountStatus = 'pending' | 'active' | 'rejected' | 'suspended'
export type Language = 'en' | 'ne'

export type TicketStatus =
  | 'reported'
  | 'verified'
  | 'in_progress'
  | 'resolved'
  | 'rejected'
  | 'merged'

export type TicketPriority = 'low' | 'medium' | 'high' | 'critical'
export type CandidateStatus = 'pending' | 'merged' | 'rejected'
export type EmergencyType = 'medical' | 'fire' | 'police' | 'disaster' | 'other'
export type SosStatus = 'open' | 'acknowledged' | 'dispatched' | 'closed'
export type AlertSeverity = 'info' | 'warning' | 'critical'

export type ServiceType =
  | 'hospital'
  | 'ambulance'
  | 'police'
  | 'fire'
  | 'ward_office'
  | 'municipality_office'
  | 'shelter'
  | 'pharmacy'
  | 'other'

export type Profile = {
  id: string
  email: string
  full_name: string | null
  phone: string | null
  role: UserRole
  account_status: AccountStatus
  municipality_id: string | null
  ward_id: string | null
  preferred_language: Language
  large_text: boolean
  high_contrast: boolean
}

export type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number | null
  profile: Profile
}

export type Category = {
  id: string
  key: string
  name_en: string
  name_ne: string
  icon: string
  match_radius_m: number
}

export type Ward = {
  id: string
  municipality_id: string
  number: number
  name_en: string | null
  name_ne: string | null
  centroid_lat: number
  centroid_lon: number
}

export type Municipality = {
  id: string
  code: string
  name_en: string
  name_ne: string
  district: string
  province: string
  type: string
}

export type MunicipalityDetail = Municipality & { wards: Ward[] }

export type CivicService = {
  id: string
  name_en: string
  name_ne: string | null
  service_type: ServiceType
  phone: string | null
  alt_phone: string | null
  address: string | null
  latitude: number | null
  longitude: number | null
  is_24x7: boolean
  is_emergency: boolean
  notes_en: string | null
  notes_ne: string | null
  distance_m: number | null
}

export type TicketSummary = {
  id: string
  public_code: string
  title: string
  description: string
  category_id: string
  status: TicketStatus
  priority: TicketPriority
  latitude: number
  longitude: number
  address_text: string | null
  ward_id: string
  municipality_id: string
  ward_number: number | null
  ward_name: string | null
  municipality_code: string | null
  parent_id: string | null
  child_count: number
  corroboration_count: number
  dispute_count: number
  community_verified: boolean
  // Distinct citizens who commented that this is urgent; raises priority.
  urgent_commenter_count: number
  // True when a human fixed the priority; automation leaves it alone.
  priority_locked: boolean
  created_at: string
  resolved_at: string | null
  distance_m: number | null
}

export type Photo = { id: string; storage_path: string; url: string | null }

export type StatusHistoryEntry = {
  from_status: TicketStatus | null
  to_status: TicketStatus
  note: string | null
  created_at: string
}

export type DuplicateCandidate = {
  id: string
  ticket_id: string
  ticket: TicketSummary | null
  candidate_ticket_id: string
  candidate: TicketSummary | null
  score: number
  category_score: number
  text_score: number
  image_score: number
  geo_score: number
  distance_m: number
  status: CandidateStatus
  explanation: string | null
}

export type TicketDetail = TicketSummary & {
  reporter_id: string
  reporter_name: string | null
  assigned_to_id: string | null
  predicted_category_key: string | null
  category_confidence: number | null
  resolution_note: string | null
  verified_at: string | null
  priority_set_at: string | null
  priority_note: string | null
  priority_set_by_name: string | null
  photos: Photo[]
  children: TicketSummary[]
  history: StatusHistoryEntry[]
  duplicate_candidates: DuplicateCandidate[]
  my_corroboration: boolean | null
}

export type TicketCreateResponse = {
  ticket: TicketDetail
  possible_duplicates: DuplicateCandidate[]
  // Set when the match was strong enough (>= 80%) to merge on the spot.
  auto_merged_into: TicketSummary | null
  auto_merge_score: number | null
}

export type TicketListResponse = { items: TicketSummary[]; total: number }

export type TicketComment = {
  id: string
  ticket_id: string
  author_id: string
  author_name: string | null
  author_role: 'citizen' | 'authority' | 'admin' | null
  body: string
  created_at: string
  // Presses for a faster fix; counts toward the ticket's priority.
  is_urgent: boolean
  is_mine: boolean
}

export type TicketCommentListResponse = { items: TicketComment[]; total: number }

export type CategoryStat = {
  key: string
  name_en: string
  name_ne: string
  total: number
  resolved: number
  median_resolution_hours: number | null
}

export type WardStat = {
  number: number
  name_en: string | null
  name_ne: string | null
  total: number
  open: number
  resolved: number
  median_resolution_hours: number | null
}

export type PublicStats = {
  municipality_code: string
  municipality_name_en: string
  municipality_name_ne: string
  total_tickets: number
  open_tickets: number
  resolved_tickets: number
  resolved_this_month: number
  median_resolution_hours: number | null
  by_category: CategoryStat[]
  by_ward: WardStat[]
  generated_at: string
}

export type SosRequest = {
  id: string
  citizen_id: string
  citizen_name: string | null
  citizen_phone: string | null
  emergency_type: EmergencyType
  latitude: number
  longitude: number
  address_text: string | null
  ward_id: string | null
  note: string | null
  contact_phone: string | null
  status: SosStatus
  acknowledged_at: string | null
  closed_at: string | null
  resolution_note: string | null
  created_at: string
}

export type SosCreateResponse = {
  sos: SosRequest
  emergency_contacts: {
    name_en: string
    name_ne: string | null
    service_type: string
    phone: string | null
    distance_m: number | null
  }[]
  message: string
}

export type Alert = {
  id: string
  title_en: string
  title_ne: string | null
  body_en: string
  body_ne: string | null
  instructions_en: string | null
  instructions_ne: string | null
  severity: AlertSeverity
  target_type: 'ward' | 'radius'
  ward_ids: string[] | null
  center_lat: number | null
  center_lon: number | null
  radius_m: number | null
  starts_at: string | null
  expires_at: string | null
  is_active: boolean
  created_at: string
  distance_m: number | null
}

export type Notification = {
  id: string
  type: string
  title_en: string
  title_ne: string | null
  body_en: string | null
  ticket_id: string | null
  alert_id: string | null
  read_at: string | null
  created_at: string
}

export type NotificationList = { items: Notification[]; unread: number }

export type ProfileList = { items: Profile[]; total: number }

export type Coords = { latitude: number; longitude: number }

export type ReverseGeocode = Coords & {
  place_name: string | null
  display_name: string | null
  // The ward a report at this point goes to (OSM's real ward when known).
  ward: Ward | null
}

export type CivicCategory =
  | 'littering'
  | 'dumping_waste'
  | 'burning_waste'
  | 'spitting'
  | 'public_urination'
  | 'smoking_in_public'
  | 'noise'
  | 'illegal_parking'
  | 'footpath_encroachment'
  | 'vandalism'
  | 'pet_waste'
  | 'other'

export type CivicStatus = 'submitted' | 'under_review' | 'action_taken' | 'dismissed'

export type CivicComplaint = {
  id: string
  public_code: string
  category: CivicCategory
  description: string
  latitude: number
  longitude: number
  address_text: string | null
  ward_id: string
  ward_number: number | null
  ward_name: string | null
  occurred_at: string
  status: CivicStatus
  action_note: string | null
  reviewed_at: string | null
  created_at: string
  photos: { id: string; url: string | null }[]
  // Only for the office handling it.
  reporter_name: string | null
  reporter_phone: string | null
}

export type CivicComplaintList = {
  items: CivicComplaint[]
  total: number
  counts: Partial<Record<CivicStatus, number>>
}

export type TravelMode = 'walk' | 'wheelchair' | 'drive'

export type Hazard = {
  id: string
  source: 'ticket' | 'alert'
  kind: string
  title: string
  severity: 'low' | 'medium' | 'high'
  latitude: number
  longitude: number
  radius_m: number
  modes: TravelMode[]
  night_only: boolean
  active_now: boolean
  avoid: boolean
  approximate: boolean
  reported_at: string | null
  reports: number
  confirmations: number
  ticket_id: string | null
  alert_id: string | null
  category_key: string | null
}

export type RouteOut = {
  line: [number, number][]
  distance_m: number
  duration_s: number
  hazard_ids: string[]
  risk: number
}

export type RoutePlan = {
  mode: TravelMode
  profile_used: TravelMode
  night: boolean
  fastest: RouteOut
  safer: RouteOut | null
  recommended: 'fastest' | 'safer'
  hazards: Hazard[]
  notes: string[]
  disclaimer: string
}

export type PlaceResult = Coords & { name: string; display_name: string }

// One row of the briefing's issue list -- real ticket data, never AI text.
export type DashboardIssue = {
  id: string
  code: string
  title: string
  priority: TicketPriority
  status: TicketStatus
  reporters: number
  age_days: number
}

export type DashboardSummary = {
  audience: 'citizen' | 'officer'
  // One short lead-in sentence -- the issue list below is the actual content.
  text: string
  // False when the model was unavailable and `text` is a templated fallback
  // built from the same numbers -- shown, not hidden, in the UI.
  ai_generated: boolean
  generated_at: string
  scope_label: string | null
  issues: DashboardIssue[]

  // citizen
  total_reports: number | null
  open_reports: number | null
  ward_open_reports: number | null

  // officer
  open_reports_officer: number | null
  needs_attention: number | null
  oldest_open_days: number | null
  top_category_name: string | null
  top_category_count: number | null
  pending_duplicates: number | null
  open_sos: number | null
  pending_civic: number | null
}
