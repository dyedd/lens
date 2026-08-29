/** Returns the persisted admin access token when browser storage is available. */
export function getStoredToken() {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem("lens_token") ?? "";
}

/** Persists the admin access token in browser storage. */
export function setStoredToken(token: string) {
  window.localStorage.setItem("lens_token", token);
}

/** Removes the persisted admin access token from browser storage. */
export function clearStoredToken() {
  window.localStorage.removeItem("lens_token");
}
