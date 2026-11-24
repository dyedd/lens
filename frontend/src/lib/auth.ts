import type { AdminProfile } from "@/lib/api/app";

export const ADMIN_TOKEN_KEY = "lens_token";
export const AUTH_CHANGE_EVENT = "lens-auth-change";

/** Returns the persisted admin access token when browser storage is available. */
export function getStoredToken() {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(ADMIN_TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

/** Pass the verified administrator ID when an account update rotates the token. */
export function setStoredToken(token: string, verifiedAdminId?: number) {
  window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
  window.dispatchEvent(
    new CustomEvent(AUTH_CHANGE_EVENT, { detail: verifiedAdminId }),
  );
}

/** Returns a non-empty token from an untrusted login response. */
export function getLoginAccessToken(value: unknown): string | null {
  if (
    typeof value !== "object" ||
    value === null ||
    !("access_token" in value)
  ) {
    return null;
  }
  const token = value.access_token;
  return typeof token === "string" && token.trim() ? token.trim() : null;
}

/** Removes the persisted admin access token from browser storage. */
export function clearStoredToken() {
  window.localStorage.removeItem(ADMIN_TOKEN_KEY);
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function isAdminProfile(value: unknown): value is AdminProfile {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "number" &&
    Number.isInteger(value.id) &&
    "username" in value &&
    typeof value.username === "string" &&
    Boolean(value.username.trim())
  );
}

export function signOut() {
  clearStoredToken();
  window.location.replace("/login");
}
