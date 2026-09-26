import type { ProtocolKind } from "./protocols";

export type HeaderRule = {
  name: string;
  action: "remove" | "override" | "append";
  value: string;
  match?: {
    path_regex?: string | null;
    model_regex?: string | null;
    protocol_regex?: string | null;
  } | null;
};
export type ParamOverrideRule = {
  path: string;
  action: "set" | "delete";
  value?: unknown;
};

export type RoutingStrategy = "round_robin" | "failover";
export type ModelGroupSyncFilterMode = "" | "contains" | "exact" | "regex";
export type ModelGroupItemState =
  | "ready"
  | "disabled"
  | "invalid"
  | "unavailable";
export type ModelGroupItemReason =
  | "manual_disabled"
  | "channel_not_found"
  | "channel_disabled"
  | "credential_not_found"
  | "credential_disabled"
  | "model_not_found"
  | "model_disabled"
  | "model_upstream_missing";
export type ModelGroupItemPayload = {
  channel_id: string;
  credential_id: string;
  model_name: string;
  enabled: boolean;
};
export type ModelGroupItem = ModelGroupItemPayload & {
  site_id: string | null;
  channel_name: string;
  protocol_config_id: string;
  protocol?: ProtocolKind | null;
  credential_name: string;
  credential_number: number;
  rate_multiplier: number | null;
  rate_source: "none" | "sub2api" | "newapi";
  state: ModelGroupItemState;
  reasons: ModelGroupItemReason[];
  sort_order: number;
  matched_by_rule: boolean;
};
export type ModelGroup = {
  id: string;
  name: string;
  client_protocols: ProtocolKind[];
  strategy: RoutingStrategy;
  route_group_id?: string;
  route_group_name?: string;
  sync_filter_mode: ModelGroupSyncFilterMode;
  sync_filter_query: string;
  param_override: ParamOverrideRule[];
  headers: HeaderRule[];
  fallback_group_ids?: string[];
  input_price_per_million: number;
  image_input_price_per_million: number;
  manual_override: boolean;
  output_price_per_million: number;
  cache_read_price_per_million: number;
  cache_write_price_per_million: number;
  image_price_per_image: number;
  pricing_mode: "free" | "tokens" | "non_tokens";
  items: ModelGroupItem[];
};
export type ModelGroupCandidateSubitem = ModelGroupItemPayload & {
  protocol_config_id: string;
  protocol: ProtocolKind;
};
export type ModelGroupCandidateItem = {
  site_id: string;
  channel_name: string;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  rate_multiplier: number | null;
  rate_source: "none" | "sub2api" | "newapi";
  base_url: string;
  model_name: string;
  protocol_config_id: string;
  protocols: ProtocolKind[];
  items: ModelGroupCandidateSubitem[];
};
export type ModelGroupCandidatesPayload = { items: ModelGroupItemPayload[] };
export type ModelGroupCandidatesResponse = {
  candidates: ModelGroupCandidateItem[];
  evaluated_items: ModelGroupItem[];
};
export type ModelGroupModelTestPayload = {
  channel_id: string;
  credential_id: string;
  model_name: string;
  prompt: string;
  protocol?: ProtocolKind;
};
