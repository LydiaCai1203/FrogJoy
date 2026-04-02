export interface Token {
  access_token: string;
  token_type: string;
}

export interface UserListItem {
  id: string;
  email: string;
  is_verified: boolean;
  is_admin: boolean;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
  last_active_at: string | null;
  book_count: number;
  total_reading_seconds: number;
}

export interface UserListResponse {
  items: UserListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserDetail extends UserListItem {
  highlight_count: number;
}

export interface UserStats {
  total_books: number;
  total_reading_seconds: number;
  total_highlights: number;
  reading_days: number;
  recent_books: Array<{
    id: string;
    title: string;
    last_opened_at: string | null;
  }>;
}

export interface OverviewStats {
  total_users: number;
  total_books: number;
  total_reading_seconds: number;
  today_active_users: number;
  verified_users: number;
  admin_users: number;
}

export interface GrowthPoint {
  date: string;
  count: number;
}

export interface ReadingStatsPoint {
  date: string;
  total_seconds: number;
  active_users: number;
}

export interface ActiveUserItem {
  user_id: string;
  email: string;
  total_reading_seconds: number;
  reading_days: number;
  last_login_at: string | null;
}

export interface SystemSettings {
  guest_rate_limit_tts: number;
  guest_rate_limit_translation: number;
  guest_rate_limit_chat: number;
  default_tts_provider: string;
  default_theme: string;
  default_font_size: number;
  allow_registration: boolean;
}
