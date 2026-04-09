let cachedToken: string | null = null

export function getStoredToken() {
  if (typeof window === 'undefined') return ''
  if (cachedToken !== null) return cachedToken
  cachedToken = window.localStorage.getItem('lens_token') ?? ''
  return cachedToken
}

export function setStoredToken(token: string) {
  cachedToken = token
  window.localStorage.setItem('lens_token', token)
}

export function clearStoredToken() {
  cachedToken = null
  window.localStorage.removeItem('lens_token')
}
