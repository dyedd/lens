import type {
  HeaderRule,
  ModelGroupReconcileReport,
  ParamOverrideRule,
} from "./groups";
import type { ProtocolKind } from "./protocols";

export type ChannelProxyMode = "inherit" | "direct" | "custom";
export type SiteBaseUrl = {
  id: string;
  url: string;
  sort_order: number;
};
export type SiteBaseUrlInput = {
  id?: string | null;
  url: string;
};
export type SiteCredential = {
  id: string;
  name: string;
  api_key: string;
  sort_order: number;
  base_url_id: string;
  rate_source: "none" | "sub2api" | "newapi";
  rate_protocol_config_id: string;
  rate_group: string;
  rate_multiplier: number | null;
  rate_observed_at: string | null;
  rate_last_synced_at: string | null;
  rate_last_error: string;
};
export type SiteCredentialInput = {
  id?: string | null;
  name: string;
  api_key: string;
  base_url_id?: string;
  rate_source: "none" | "sub2api" | "newapi";
  rate_protocol_config_id: string;
  rate_group: string;
};
export type SiteModel = {
  id: string;
  protocol?: ProtocolKind | null;
  credential_id: string;
  credential_name: string;
  model_name: string;
  enabled: boolean;
  sort_order: number;
  upstream_missing: boolean;
  /** Admin override; null falls back to the upstream or model-name value. */
  context_window: number | null;
  /** Context window the upstream model list reports. */
  upstream_context_window: number | null;
};
export type SiteModelInput = {
  id?: string | null;
  protocol?: ProtocolKind;
  credential_id: string;
  model_name: string;
  enabled: boolean;
  upstream_missing: boolean;
  context_window: number | null;
  upstream_context_window: number | null;
};
export type SiteProtocolConfig = {
  id: string;
  base_url_id: string;
  protocols: ProtocolKind[];
  credential_ids: string[];
  models: SiteModel[];
  sync_targets: SiteSyncTarget[];
};
export type SiteProtocolConfigInput = {
  id?: string | null;
  base_url_id: string;
  protocols: ProtocolKind[];
  models: SiteModelInput[];
  sync_targets: SiteSyncTarget[];
};
export type SiteSyncTarget = {
  credential_id: string;
  protocol: ProtocolKind;
  model_name: string;
};
export type Site = {
  id: string;
  name: string;
  enabled: boolean;
  tags: string[];
  updated_at?: string | null;
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  headers: HeaderRule[];
  param_override: ParamOverrideRule[];
  base_urls: SiteBaseUrl[];
  credentials: SiteCredential[];
  protocols: SiteProtocolConfig[];
};
export type HealthTier =
  | "no-data"
  | "healthy"
  | "mostly-healthy"
  | "partial"
  | "major"
  | "all-failed";
export type HealthBucket = {
  started_at: string;
  ended_at: string;
  success_count: number;
  total_count: number;
  tier: HealthTier;
};
export type HealthItem = {
  name: string;
  success_count: number;
  total_count: number;
  tier: HealthTier;
  buckets: HealthBucket[];
};
export type HealthSummary = {
  started_at: string;
  ended_at: string;
  items: HealthItem[];
  next_offset: number | null;
};
export type SitePayload = {
  name: string;
  tags: string[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  headers: HeaderRule[];
  param_override: ParamOverrideRule[];
  base_urls: SiteBaseUrlInput[];
  credentials: SiteCredentialInput[];
  protocols: SiteProtocolConfigInput[];
};
export type ChannelModelSyncResultItem = {
  site_id: string;
  site_name: string;
  protocol_config_id: string;
  credential_id: string;
  credential_name: string;
  status: "updated" | "unchanged" | "failed";
  error: string;
  added: string[];
  missing: string[];
  restored: string[];
};
/** One model sync run: per-key catalog changes, then where models ended up. */
export type ChannelModelSyncResponse = {
  /** Empty when nothing was synced and the run was not recorded. */
  id: string;
  started_at: string | null;
  finished_at: string | null;
  items: ChannelModelSyncResultItem[];
  groups: ModelGroupReconcileReport;
};
export type SiteBatchImportBaseUrlInput = {
  ref: string;
  url: string;
};
export type SiteBatchImportCredentialInput = {
  ref: string;
  name?: string;
  api_key: string;
  base_url_ref?: string;
};
export type SiteBatchImportModelInput = {
  model_name: string;
  credential_ref: string;
  enabled?: boolean;
};
export type SiteBatchImportProtocolInput = {
  protocol?: ProtocolKind;
  base_url_ref: string;
  credential_refs: string[];
  models?: SiteBatchImportModelInput[];
};
export type SiteBatchImportItem = {
  name: string;
  enabled: boolean;
  tags: string[];
  proxy_mode?: ChannelProxyMode;
  channel_proxy?: string;
  headers?: HeaderRule[];
  param_override?: ParamOverrideRule[];
  base_urls: SiteBatchImportBaseUrlInput[];
  credentials: SiteBatchImportCredentialInput[];
  protocols: SiteBatchImportProtocolInput[];
};
export type SiteBatchImportPayload = { sites: SiteBatchImportItem[] };
export type SiteBatchImportFieldError = {
  field: string;
  message: string;
};
type SiteBatchImportItemIdentity = { index: number; name: string };
export type SiteBatchImportItemResult = SiteBatchImportItemIdentity &
  (
    | { status: "created"; reason: ""; site: Site; errors: [] }
    | {
        status: "skipped";
        reason: "duplicate_name" | "duplicate_in_file";
        site: null;
        errors: [];
      }
    | {
        status: "error";
        reason: "";
        site: null;
        errors: SiteBatchImportFieldError[];
      }
    | {
        status: "not_committed";
        reason: "batch_validation_failed";
        site: null;
        errors: [];
      }
  );
export type SiteBatchImportResult = {
  committed: boolean;
  created_count: number;
  skipped_count: number;
  error_count: number;
  not_committed_count: number;
  items: SiteBatchImportItemResult[];
};
export type SiteModelFetchPayload = {
  base_url: string;
  /** Picks the list endpoint and auth headers. */
  protocol: ProtocolKind;
  headers: HeaderRule[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  credentials: {
    id?: string | null;
    name: string;
    api_key: string;
  }[];
  credential_ids: string[];
};
export type SiteModelFetchItem = {
  credential_id: string;
  credential_name: string;
  model_name: string;
  context_window: number | null;
};
export type SiteModelTestPayload = {
  protocol: ProtocolKind;
  base_url: string;
  headers: HeaderRule[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  param_override: ParamOverrideRule[];
  credential: { id: string; name: string; api_key: string };
  model_name: string;
  prompt: string;
};
export type SiteModelTestResult = {
  success: boolean;
  status_code: number | null;
  latency_ms: number;
  model_name: string;
  credential_id: string;
  output_text: string;
  error_message: string;
  debug?: {
    request: {
      method: string;
      path: string;
      headers: Record<string, string>;
      body: unknown;
    };
    response: {
      headers: Record<string, string>;
      body: string;
    };
  } | null;
};
