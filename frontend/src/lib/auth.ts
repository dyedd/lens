/** Returns the persisted admin access token when browser storage is available. */
export function getStoredToken() {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem("lens_token") ?? "";
}

/** Keep a protected route when a session check fails with a token still present. */
export function shouldRedirectAfterSessionCheckFailure(token: string) {
  return token.length === 0;
}

/** Persists the admin access token in browser storage. */
export function setStoredToken(token: string) {
  window.localStorage.setItem("lens_token", token);
  clearCachedProfile();
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
  window.localStorage.removeItem("lens_token");
  clearCachedProfile();
}
export const SESSION_CACHE_KEY = "lens_admin_profile_cache";

export function signOut() {
  clearStoredToken();
  window.location.replace("/login");
}

function clearCachedProfile() {
  try {
    window.sessionStorage.removeItem(SESSION_CACHE_KEY);
  } catch {
    // 浏览器禁用临时存储时，仍需完成会话切换。
  }
}
