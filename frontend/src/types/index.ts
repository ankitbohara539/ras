export const roles = ["CITIZEN", "AUTHORITY", "RESPONDER", "ADMIN"] as const;
export type Role = (typeof roles)[number];
export type AccountStatus = "ACTIVE" | "SUSPENDED" | "DISABLED";

export type CurrentUser = {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  avatar_url: string | null;
  preferred_language: string;
  status: AccountStatus;
  roles: Role[];
  created_at: string;
};

export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type Issue = {
  id: string;
  reporter_id: string;
  category_id: string;
  administrative_area_id: string | null;
  title: string;
  description: string;
  status: string;
  severity: string;
  address_text: string | null;
  client_request_id: string;
  created_at: string;
  distance_meters?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  confirmations: number;
};

export type Notification = {
  id: string;
  event_type: string;
  title: string;
  body: string;
  created_at: string;
  read_at: string | null;
};
