export function getStoredToken() {
  if (typeof window === 'undefined') {
    return ''
  }
  return window.localStorage.getItem('lens_token') ?? ''
}

export function setStoredToken(token: string) {
  window.localStorage.setItem('lens_token', token)
}

export function clearStoredToken() {
  window.localStorage.removeItem('lens_token')
}
