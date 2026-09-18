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
  parent_id: string | null
  child_count: number
  corroboration_count: number
  dispute_count: number
  community_verified: boolean
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
  photos: Photo[]
  children: TicketSummary[]
  history: StatusHistoryEntry[]
  duplicate_candidates: DuplicateCandidate[]
  my_corroboration: boolean | null
}

export type TicketCreateResponse = {
  ticket: TicketDetail
  possible_duplicates: DuplicateCandidate[]
}

export type TicketListResponse = { items: TicketSummary[]; total: number }

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
