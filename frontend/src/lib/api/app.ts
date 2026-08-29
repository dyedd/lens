export const ADMIN_PASSWORD_MIN_LENGTH = 12;
export type PublicBranding = { site_name: string; logo_url: string };
export type AppInfo = {
  system_version: string;
  site_name: string;
  logo_url: string;
  time_zone: string;
};
export type VersionCheckResult = {
  current_version: string;
  latest_version: string;
  release_url: string;
  has_update: boolean;
  checked_at: string;
};
export type AdminProfile = { id: number; username: string };
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
