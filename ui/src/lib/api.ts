export type ProtocolKind = 'openai_chat' | 'openai_responses' | 'anthropic' | 'gemini'

export type RoutingStrategy = 'round_robin' | 'failover'

export type ModelGroupItem = {
  channel_id: string
  channel_name: string
  credential_id: string
  credential_name: string
  model_name: string
  enabled: boolean
  sort_order: number
}

export type ModelGroup = {
  id: string
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  route_group_id?: string
  route_group_name?: string
  input_price_per_million: number
  output_price_per_million: number
  cache_read_price_per_million: number
  cache_write_price_per_million: number
  items: ModelGroupItem[]
}

export type ModelGroupItemPayload = {
  channel_id: string
  credential_id: string
  model_name: string
  enabled: boolean
}

export type ModelGroupPayload = {
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  route_group_id?: string
  items: ModelGroupItemPayload[]
}

export type ModelGroupCandidateItem = {
  channel_id: string
  channel_name: string
  credential_id: string
  credential_name: string
  base_url: string
  model_name: string
}

export type SiteBaseUrl = {
  id: string
  url: string
  name: string
  enabled: boolean
  sort_order: number
}

export type SiteBaseUrlInput = {
  id?: string | null
  url: string
  name: string
  enabled: boolean
}

export type SiteCredential = {
  id: string
  name: string
  api_key: string
  enabled: boolean
  sort_order: number
}

export type SiteCredentialInput = {
  id?: string | null
  name: string
  api_key: string
  enabled: boolean
}

export type SiteProtocolCredentialBinding = {
  credential_id: string
  credential_name: string
  enabled: boolean
  sort_order: number
}

export type SiteProtocolCredentialBindingInput = {
  credential_id: string
  enabled: boolean
}

export type SiteModel = {
  id: string
  credential_id: string
  credential_name: string
  model_name: string
  enabled: boolean
  sort_order: number
}

export type SiteModelInput = {
  id?: string | null
  credential_id: string
  model_name: string
  enabled: boolean
}

export type SiteProtocolConfig = {
  id: string
  protocol: ProtocolKind
  enabled: boolean
  headers: Record<string, string>
  channel_proxy: string
  param_override: string
  match_regex: string
  base_url_id: string
  bindings: SiteProtocolCredentialBinding[]
  models: SiteModel[]
}

export type SiteProtocolConfigInput = {
  id?: string | null
  protocol: ProtocolKind
  enabled: boolean
  headers: Record<string, string>
  channel_proxy: string
  param_override: string
  match_regex: string
  base_url_id: string
  bindings: SiteProtocolCredentialBindingInput[]
  models: SiteModelInput[]
}

export type Site = {
  id: string
  name: string
  base_urls: SiteBaseUrl[]
  credentials: SiteCredential[]
  protocols: SiteProtocolConfig[]
}

export type SiteRuntimeSummary = {
  site_id: string
  site_name: string
  latest_request_at?: string | null
  latest_success?: boolean | null
  latest_status_code?: number | null
  latest_error_message?: string | null
  latest_channel_id?: string | null
  latest_channel_name?: string | null
}

export type SitePayload = {
  name: string
  base_urls: SiteBaseUrlInput[]
  credentials: SiteCredentialInput[]
  protocols: SiteProtocolConfigInput[]
}

export type SiteModelFetchPayload = {
  protocol: ProtocolKind
  base_url: string
  headers: Record<string, string>
  channel_proxy: string
  match_regex: string
  credentials: SiteCredentialInput[]
  bindings: SiteProtocolCredentialBindingInput[]
}

export type SiteModelFetchItem = {
  credential_id: string
  credential_name: string
  model_name: string
}

export type ModelGroupCandidatesPayload = {
  protocol?: ProtocolKind
  exclude_items: ModelGroupItemPayload[]
}

export type ModelGroupCandidatesResponse = {
  candidates: ModelGroupCandidateItem[]
}

export type ModelPriceItem = {
  model_key: string
  display_name: string
  protocols: ProtocolKind[]
  input_price_per_million: number
  output_price_per_million: number
  cache_read_price_per_million: number
  cache_write_price_per_million: number
}

export type ModelPriceListResponse = {
  items: ModelPriceItem[]
  last_synced_at?: string | null
}

export type ModelPriceUpdatePayload = {
  model_key: string
  display_name: string
  input_price_per_million: number
  output_price_per_million: number
  cache_read_price_per_million: number
  cache_write_price_per_million: number
}

export type SettingItem = {
  key: string
  value: string
}

export type PublicBranding = {
  site_name: string
  logo_url: string
}

export type AppInfo = {
  system_version: string
  site_name: string
  logo_url: string
}


export type AdminProfile = {
  id: number
  username: string
}

export type AdminPasswordChangePayload = {
  current_password: string
  new_password: string
}

export type AdminProfileUpdatePayload = {
  username: string
  current_password: string
  new_password: string
}

export type AdminProfileUpdateResponse = {
  access_token: string
  token_type: string
  expires_in: number
  profile: AdminProfile
}

export type RouteSnapshot = {
  routes: Array<{ protocol: ProtocolKind; next_index: number; channel_ids: string[] }>
  health: Array<{ channel_id: string; consecutive_failures: number; last_error?: string | null }>
}

export type RoutePreview = {
  protocol: ProtocolKind
  requested_group_name?: string | null
  resolved_group_name?: string | null
  strategy?: RoutingStrategy | null
  matched_channel_ids: string[]
  items: Array<{ channel_id: string; channel_name: string; model_name?: string | null }>
}

export type OverviewMetrics = {
  total_requests: number
  successful_requests: number
  failed_requests: number
  avg_latency_ms: number
  active_gateway_keys: number
  enabled_groups: number
  enabled_channels: number
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
  requested_group_name?: string | null
  resolved_group_name?: string | null
  upstream_model_name?: string | null
  channel_id?: string | null
  channel_name?: string | null
  gateway_key_id?: string | null
  status_code: number
  success: boolean
  is_stream: boolean
  first_token_latency_ms: number
  latency_ms: number
  input_tokens: number
  cache_read_input_tokens: number
  cache_write_input_tokens: number
  output_tokens: number
  total_tokens: number
  input_cost_usd: number
  output_cost_usd: number
  total_cost_usd: number
  attempt_count: number
  error_message?: string | null
  created_at: string
}

export type RequestLogAttempt = {
  channel_id: string
  channel_name: string
  model_name?: string | null
  status_code?: number | null
  success: boolean
  duration_ms: number
  error_message?: string | null
}

export type RequestLogDetail = RequestLogItem & {
  request_content?: string | null
  response_content?: string | null
  attempts: RequestLogAttempt[]
}

export type RequestLogPage = {
  items: RequestLogItem[]
  total: number
  limit: number
  offset: number
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
