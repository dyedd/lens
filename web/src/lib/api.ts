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

export type OverviewMetrics = {
  total_requests: number
  successful_requests: number
  failed_requests: number
  avg_latency_ms: number
  active_gateway_keys: number
  enabled_groups: number
  enabled_providers: number
}

export type OverviewSummaryMetric = {
  value: number
  delta: number
}

export type OverviewSummary = {
  request_count: OverviewSummaryMetric
  wait_time_ms: OverviewSummaryMetric
  total_tokens: OverviewSummaryMetric
  total_cost_usd: OverviewSummaryMetric
  input_tokens: OverviewSummaryMetric
  input_cost_usd: OverviewSummaryMetric
  output_tokens: OverviewSummaryMetric
  output_cost_usd: OverviewSummaryMetric
}

export type OverviewDailyPoint = {
  date: string
  request_count: number
  total_tokens: number
  total_cost_usd: number
  wait_time_ms: number
  successful_requests: number
  failed_requests: number
}

export type OverviewModelMetricPoint = {
  model: string
  requests: number
  total_tokens: number
  total_cost_usd: number
}

export type OverviewModelTrendPoint = {
  date: string
  model: string
  value: number
}

export type OverviewModelAnalytics = {
  distribution: OverviewModelMetricPoint[]
  request_ranking: OverviewModelMetricPoint[]
  trend: OverviewModelTrendPoint[]
  available_models: string[]
}

export type RequestLogItem = {
  id: number
  protocol: ProtocolKind
  requested_model?: string | null
  matched_group_name?: string | null
  provider_id?: string | null
  gateway_key_id?: string | null
  status_code: number
  success: boolean
  latency_ms: number
  resolved_model?: string | null
  input_tokens: number
  output_tokens: number
  total_tokens: number
  input_cost_usd: number
  output_cost_usd: number
  total_cost_usd: number
  error_message?: string | null
  created_at: string
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
