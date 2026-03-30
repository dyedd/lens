export type ProtocolKind = 'openai_chat' | 'openai_responses' | 'anthropic' | 'gemini'

export type ProviderStatus = 'enabled' | 'disabled'

export type RoutingStrategy = 'round_robin' | 'weighted' | 'failover'

export type Provider = {
  id: string
  name: string
  protocol: ProtocolKind
  base_url: string
  api_key: string
  model_name?: string | null
  status: ProviderStatus
  weight: number
  priority: number
  headers: Record<string, string>
  model_patterns: string[]
}

export type ProviderPayload = {
  name: string
  protocol: ProtocolKind
  base_url: string
  api_key: string
  model_name?: string | null
  status: ProviderStatus
  weight: number
  priority: number
  headers: Record<string, string>
  model_patterns: string[]
}

export type ModelGroup = {
  id: string
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  provider_ids: string[]
  enabled: boolean
}

export type ModelGroupPayload = {
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  provider_ids: string[]
  enabled: boolean
}

export type GatewayKey = {
  id: string
  name: string
  secret: string
  enabled: boolean
}

export type GatewayKeyPayload = {
  name: string
  enabled: boolean
}

export type SettingItem = {
  key: string
  value: string
}

export type AdminProfile = {
  id: number
  username: string
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

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type') ?? ''

  if (contentType.includes('application/json')) {
    const payload = await response.json().catch(() => null)
    const detail = payload?.detail
    if (typeof detail === 'string' && detail) {
      return detail
    }
    const message = payload?.error?.message
    if (typeof message === 'string' && message) {
      return message
    }
  }

  const text = await response.text()
  return text || ('Request failed with status ' + response.status)
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !headers.has('content-type')) {
    headers.set('content-type', 'application/json')
  }

  const token = getToken()
  if (token) {
    headers.set('authorization', 'Bearer ' + token)
  }

  const response = await fetch('/api' + path, { ...init, headers })
  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
