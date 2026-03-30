export type ProtocolKind = 'openai_chat' | 'openai_responses' | 'anthropic' | 'gemini'

export type Provider = {
  id: string
  name: string
  protocol: ProtocolKind
  base_url: string
  api_key: string
  model_name?: string | null
  status: 'enabled' | 'disabled'
  weight: number
  priority: number
  headers: Record<string, string>
  model_patterns: string[]
}

export type ModelGroup = {
  id: string
  name: string
  protocol: ProtocolKind
  strategy: 'round_robin' | 'weighted' | 'failover'
  provider_ids: string[]
  enabled: boolean
}

export type GatewayKey = {
  id: string
  name: string
  secret: string
  enabled: boolean
}

export type SettingItem = {
  key: string
  value: string
}

export type RouteSnapshot = {
  routes: Array<{ protocol: ProtocolKind; next_index: number; provider_ids: string[] }>
  health: Array<{ provider_id: string; consecutive_failures: number; last_error?: string | null }>
}

function getToken() {
  if (typeof window === 'undefined') {
    return ''
  }
  return window.localStorage.getItem('lens_token') ?? ''
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('content-type', 'application/json')
  const token = getToken()
  if (token) {
    headers.set('authorization', `Bearer ${token}`)
  }

  const response = await fetch(`/api${path}`, { ...init, headers })
  if (!response.ok) {
    throw new Error(await response.text())
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
