import type {
  HeaderRule,
  ModelGroupEnsureFromSiteResponse,
  ModelGroupEnsureModelInput,
  ParamOverrideRule,
} from "./groups";
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
  enabled: boolean;
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
  source: "manual" | "synced";
};
export type SiteModelInput = {
  id?: string | null;
  protocol: ProtocolKind;
  credential_id: string;
  model_name: string;
  enabled: boolean;
  source: "manual" | "synced";
};
export type SiteSyncTarget = {
  credential_id: string;
  model_name: string;
  protocol: ProtocolKind;
};
export type SiteProtocolConfig = {
  id: string;
  name: string;
  protocols: ProtocolKind[];
  enabled: boolean;
  headers: HeaderRule[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  param_override: ParamOverrideRule[];
  base_url_id: string;
  credential_ids: string[];
  sync_targets: SiteSyncTarget[];
  models: SiteModel[];
};
export type SiteProtocolConfigInput = {
  id?: string | null;
  name: string;
  protocols: ProtocolKind[];
  enabled: boolean;
  headers: HeaderRule[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  param_override: ParamOverrideRule[];
  base_url_id: string;
  credential_ids: string[];
  sync_targets: SiteSyncTarget[];
  models: SiteModelInput[];
};
export type Site = {
  id: string;
  name: string;
  enabled: boolean;
  tags: string[];
  base_urls: SiteBaseUrl[];
  credentials: SiteCredential[];
  protocols: SiteProtocolConfig[];
};
export type HealthBucket = {
  started_at: string;
  ended_at: string;
  success_count: number;
  total_count: number;
};
export type HealthItem = {
  name: string;
  success_count: number;
  total_count: number;
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
  base_urls: SiteBaseUrlInput[];
  credentials: SiteCredentialInput[];
  protocols: SiteProtocolConfigInput[];
};
export type SiteModelGroupSavePayload = SitePayload & {
  site_id?: string | null;
  dry_run: boolean;
  models: ModelGroupEnsureModelInput[] | null;
};
export type SiteModelGroupSaveResponse = {
  site: Site;
  model_groups: ModelGroupEnsureFromSiteResponse;
};
export type SiteBatchImportBaseUrlInput = {
  ref: string;
  url: string;
  name?: string;
  enabled?: boolean;
};
export type SiteBatchImportCredentialInput = {
  ref: string;
  name?: string;
  api_key: string;
  enabled?: boolean;
};
export type SiteBatchImportModelInput = {
  model_name: string;
  credential_ref: string;
  enabled?: boolean;
  source?: "manual" | "synced";
};
export type SiteBatchImportProtocolInput = {
  name: string;
  protocol: ProtocolKind;
  enabled?: boolean;
  headers?: HeaderRule[];
  proxy_mode?: ChannelProxyMode;
  channel_proxy?: string;
  param_override?: ParamOverrideRule[];
  base_url_ref: string;
  credential_refs: string[];
  models?: SiteBatchImportModelInput[];
};
export type SiteBatchImportItem = {
  name: string;
  enabled: boolean;
  tags: string[];
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
  headers: HeaderRule[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  match_regex: string;
  credentials: {
    id?: string | null;
    name: string;
    api_key: string;
    enabled: boolean;
  }[];
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
};
