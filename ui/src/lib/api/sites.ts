import type { ProtocolKind } from "./protocols";

export type ChannelProxyMode = "inherit" | "direct" | "custom";
export type SiteBaseUrl = {
  id: string;
  url: string;
  name: string;
  enabled: boolean;
  sort_order: number;
  supported_protocols: ProtocolKind[];
};
export type SiteBaseUrlInput = {
  id?: string | null;
  url: string;
  name: string;
  enabled: boolean;
  supported_protocols: ProtocolKind[];
};
export type SiteCredential = {
  id: string;
  name: string;
  api_key: string;
  enabled: boolean;
  sort_order: number;
};
export type SiteCredentialInput = {
  id?: string | null;
  name: string;
  api_key: string;
  enabled: boolean;
};
export type SiteModel = {
  id: string;
  protocol?: ProtocolKind | null;
  credential_id: string;
  credential_name: string;
  model_name: string;
  enabled: boolean;
  sort_order: number;
};
export type SiteModelInput = {
  id?: string | null;
  protocol: ProtocolKind;
  credential_id: string;
  model_name: string;
  enabled: boolean;
};
export type SiteProtocolConfig = {
  id: string;
  name: string;
  protocols: ProtocolKind[];
  enabled: boolean;
  headers: Record<string, string>;
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  param_override: string;
  match_regex: string;
  base_url_id: string;
  credential_id: string;
  auto_sync_enabled: boolean;
  models: SiteModel[];
};
export type SiteProtocolConfigInput = {
  id?: string | null;
  name: string;
  protocols: ProtocolKind[];
  enabled: boolean;
  headers: Record<string, string>;
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  param_override: string;
  match_regex: string;
  base_url_id: string;
  credential_id: string;
  auto_sync_enabled: boolean;
  models: SiteModelInput[];
};
export type Site = {
  id: string;
  name: string;
  base_urls: SiteBaseUrl[];
  credentials: SiteCredential[];
  protocols: SiteProtocolConfig[];
};
export type SiteChannelHealthBucket = {
  started_at: string;
  ended_at: string;
  success_count: number;
  total_count: number;
};
export type SiteChannelRuntimeSummary = {
  channel_id: string;
  health_buckets: SiteChannelHealthBucket[];
};
export type SiteRuntimeSummary = {
  site_id: string;
  site_name: string;
  recent_request_count: number;
  latest_request_at?: string | null;
  latest_success?: boolean | null;
  latest_status_code?: number | null;
  latest_error_message?: string | null;
  latest_channel_id?: string | null;
  latest_channel_name?: string | null;
  channel_summaries: SiteChannelRuntimeSummary[];
};
export type SitePayload = {
  name: string;
  base_urls: SiteBaseUrlInput[];
  credentials: SiteCredentialInput[];
  protocols: SiteProtocolConfigInput[];
};
export type SiteBatchImportBaseUrlInput = {
  ref?: string;
  url: string;
  name?: string;
  enabled?: boolean;
};
export type SiteBatchImportCredentialInput = {
  ref?: string;
  name?: string;
  api_key: string;
  enabled?: boolean;
};
export type SiteBatchImportModelInput = {
  model_name: string;
  credential_ref?: string;
  enabled?: boolean;
};
export type SiteBatchImportProtocolInput = {
  protocol: ProtocolKind;
  enabled?: boolean;
  headers?: Record<string, string>;
  proxy_mode?: ChannelProxyMode;
  channel_proxy?: string;
  param_override?: string;
  match_regex?: string;
  base_url_ref?: string;
  credential_ref?: string;
  models?: SiteBatchImportModelInput[];
};
export type SiteBatchImportItem = {
  name: string;
  base_urls: SiteBatchImportBaseUrlInput[];
  credentials: SiteBatchImportCredentialInput[];
  protocols: SiteBatchImportProtocolInput[];
};
export type SiteBatchImportPayload = { sites: SiteBatchImportItem[] };
export type SiteBatchImportSkipped = {
  index: number;
  name: string;
  reason: string;
};
export type SiteBatchImportError = {
  index: number;
  field: string;
  message: string;
};
export type SiteBatchImportResult = {
  committed: boolean;
  created_count: number;
  skipped_count: number;
  error_count: number;
  created: Site[];
  skipped: SiteBatchImportSkipped[];
  errors: SiteBatchImportError[];
};
export type SiteModelFetchPayload = {
  base_url: string;
  headers: Record<string, string>;
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  match_regex: string;
  credentials: SiteCredentialInput[];
  credential_ids: string[];
};
export type SiteModelFetchItem = {
  credential_id: string;
  credential_name: string;
  model_name: string;
};
export type SiteModelTestPayload = {
  protocol: ProtocolKind;
  base_url: string;
  headers: Record<string, string>;
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  param_override: string;
  credential: { id: string; name: string; api_key: string };
  model_name: string;
  prompt: string;
};
export type SiteModelTestResult = {
  success: boolean;
  status_code?: number | null;
  latency_ms: number;
  model_name: string;
  credential_id: string;
  output_text: string;
  error_message: string;
};
