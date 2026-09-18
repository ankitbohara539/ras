import type {
  Alert,
  Category,
  CivicService,
  Coords,
  DuplicateCandidate,
  MunicipalityDetail,
  Municipality,
  NotificationList,
  Profile,
  ProfileList,
  ServiceType,
  SosCreateResponse,
  SosRequest,
  SosStatus,
  TicketCreateResponse,
  TicketDetail,
  TicketListResponse,
  TicketPriority,
  TicketStatus,
  TokenResponse,
  Ward,
} from './types'

const API_URL = import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? ''
const TOKEN_KEY = 'sahayatri.access_token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Private browsing: the session simply will not survive a reload.
  }
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

type RequestOptions = {
  method?: string
  body?: unknown
  auth?: boolean
  formData?: FormData
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, formData } = options

  const headers: Record<string, string> = {}
  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  if (body !== undefined && !formData) headers['Content-Type'] = 'application/json'

  const response = await fetch(`${API_URL}/api${path}`, {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  })

  if (response.status === 204) return undefined as T

  const text = await response.text()
  const payload = text ? JSON.parse(text) : null

  if (!response.ok) {
    // FastAPI sends `detail` as a string, or an array for validation errors.
    const detail = payload?.detail
    let message = 'Something went wrong.'
    if (typeof detail === 'string') message = detail
    else if (Array.isArray(detail) && detail.length > 0) {
      message = detail
        .map((d: { loc?: string[]; msg?: string }) => {
          const field = d.loc?.filter((p) => p !== 'body').join('.')
          return field ? `${field}: ${d.msg}` : d.msg
        })
        .join('; ')
    }
    throw new ApiError(response.status, message)
  }

  return payload as T
}

function query(params: Record<string, unknown>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  // -- auth ----------------------------------------------------------
  login: (email: string, password: string) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    }),

  register: (payload: {
    email: string
    password: string
    full_name: string
    phone?: string
    requested_role?: 'citizen' | 'authority'
    ward_id?: string
    municipality_id?: string
    preferred_language?: 'en' | 'ne'
  }) =>
    request<{ profile: Profile; requires_approval: boolean; message: string }>(
      '/auth/register',
      { method: 'POST', body: payload, auth: false },
    ),

  me: () => request<Profile>('/users/me'),

  updateMe: (payload: Partial<Profile>) =>
    request<Profile>('/users/me', { method: 'PATCH', body: payload }),

  // -- reference (public) --------------------------------------------
  categories: () => request<Category[]>('/categories', { auth: false }),

  municipalities: () => request<Municipality[]>('/municipalities', { auth: false }),

  municipality: (id: string) =>
    request<MunicipalityDetail>(`/municipalities/${id}`, { auth: false }),

  nearestWard: (coords: Coords) =>
    request<Ward>(`/wards/nearest${query({ ...coords })}`, { auth: false }),

  services: (params: {
    service_type?: ServiceType
    emergency_only?: boolean
    search?: string
    latitude?: number
    longitude?: number
    radius_m?: number
  }) => request<CivicService[]>(`/services${query(params)}`, { auth: false }),

  // -- tickets -------------------------------------------------------
  createTicket: (
    payload: {
      description: string
      latitude: number
      longitude: number
      title?: string
      category_id?: string
      address_text?: string
      description_lang?: 'en' | 'ne'
    },
    photos: File[],
  ) => {
    const form = new FormData()
    form.append('payload', JSON.stringify(payload))
    for (const photo of photos) form.append('photos', photo)
    return request<TicketCreateResponse>('/tickets', {
      method: 'POST',
      formData: form,
    })
  },

  tickets: (params: {
    status?: TicketStatus
    category_id?: string
    ward_id?: string
    mine?: boolean
    parents_only?: boolean
    search?: string
    limit?: number
    offset?: number
  }) => request<TicketListResponse>(`/tickets${query(params)}`),

  nearbyTickets: (coords: Coords, radius_m = 1000) =>
    request<TicketListResponse>(`/tickets/nearby${query({ ...coords, radius_m })}`),

  ticket: (id: string) => request<TicketDetail>(`/tickets/${id}`),

  corroborate: (
    id: string,
    payload: { is_confirmed: boolean; latitude: number; longitude: number; note?: string },
  ) =>
    request<{
      ticket_id: string
      corroboration_count: number
      dispute_count: number
      community_verified: boolean
      distance_m: number
      message: string
    }>(`/tickets/${id}/corroborate`, { method: 'POST', body: payload }),

  updateTicketStatus: (
    id: string,
    payload: { status: TicketStatus; note?: string; resolution_note?: string },
  ) => request<TicketDetail>(`/tickets/${id}/status`, { method: 'PATCH', body: payload }),

  assignTicket: (
    id: string,
    payload: { assigned_to_id?: string | null; priority?: TicketPriority },
  ) => request<TicketDetail>(`/tickets/${id}/assign`, { method: 'PATCH', body: payload }),

  mergeTicket: (id: string, parent_ticket_id: string, note?: string) =>
    request<TicketDetail>(`/tickets/${id}/merge`, {
      method: 'POST',
      body: { parent_ticket_id, note },
    }),

  splitTicket: (id: string) =>
    request<TicketDetail>(`/tickets/${id}/split`, { method: 'POST' }),

  reviewQueue: (limit = 25) =>
    request<DuplicateCandidate[]>(`/tickets/review/queue${query({ limit })}`),

  dismissCandidate: (candidateId: string) =>
    request<DuplicateCandidate>(`/tickets/candidates/${candidateId}/reject`, {
      method: 'POST',
    }),

  // -- emergency -----------------------------------------------------
  raiseSos: (payload: {
    emergency_type: string
    latitude: number
    longitude: number
    note?: string
    contact_phone?: string
  }) => request<SosCreateResponse>('/sos', { method: 'POST', body: payload }),

  sosList: (status?: SosStatus) => request<SosRequest[]>(`/sos${query({ status })}`),

  updateSos: (id: string, payload: { status: SosStatus; resolution_note?: string }) =>
    request<SosRequest>(`/sos/${id}`, { method: 'PATCH', body: payload }),

  alerts: (coords?: Coords) =>
    request<Alert[]>(`/alerts${coords ? query({ ...coords }) : ''}`),

  publishAlert: (payload: Record<string, unknown>) =>
    request<Alert>('/alerts', { method: 'POST', body: payload }),

  deactivateAlert: (id: string) =>
    request<Alert>(`/alerts/${id}/deactivate`, { method: 'PATCH' }),

  notifications: (unread_only = false) =>
    request<NotificationList>(`/notifications${query({ unread_only })}`),

  markNotificationsRead: () =>
    request<NotificationList>('/notifications/read', { method: 'POST' }),

  // -- admin ---------------------------------------------------------
  pendingAuthorities: () => request<ProfileList>('/admin/profiles/pending'),

  allProfiles: (params: { role?: string; account_status?: string; search?: string }) =>
    request<ProfileList>(`/admin/profiles${query(params)}`),

  approveAuthority: (id: string, payload: { ward_id?: string; note?: string }) =>
    request<Profile>(`/admin/profiles/${id}/approve`, { method: 'POST', body: payload }),

  rejectAuthority: (id: string, reason: string) =>
    request<Profile>(`/admin/profiles/${id}/reject`, {
      method: 'POST',
      body: { reason },
    }),
}
