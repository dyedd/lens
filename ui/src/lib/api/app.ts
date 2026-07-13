import type { ProtocolKind } from "./protocols";
export type PublicBranding = { site_name: string; logo_url: string };
export type AppInfo = {
  system_version: string;
  site_name: string;
  logo_url: string;
  time_zone: string;
  protocol_conversions?: Record<string, string[]>;
};
export type VersionCheckResult = {
  current_version: string;
  latest_version: string;
  release_url: string;
  has_update: boolean;
  checked_at: string;
};
export type AdminProfile = { id: number; username: string };
export type AdminPasswordChangePayload = {
  current_password: string;
  new_password: string;
};
export type AdminProfileUpdatePayload = {
  username: string;
  current_password: string;
  new_password: string;
};
export type AdminProfileUpdateResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  profile: AdminProfile;
};
export type RouteSnapshot = {
  routes: Array<{
    protocol: ProtocolKind;
    next_index: number;
    next_channel_id?: string | null;
    channel_ids: string[];
    available_channel_ids: string[];
    cooldown_channel_ids: string[];
  }>;
  health: Array<{
    channel_id: string;
    consecutive_failures: number;
    last_error?: string | null;
    last_error_category?: string | null;
    opened_until: number;
    cooldown_remaining_seconds: number;
    last_cooldown_seconds: number;
    score: number;
    available: boolean;
    available_key_count: number;
    cooled_key_count: number;
    key_health: Array<{
      credential_id: string;
      consecutive_failures: number;
      cooled_until: number;
      cooldown_remaining_seconds: number;
      last_cooldown_seconds: number;
      available: boolean;
    }>;
  }>;
};
