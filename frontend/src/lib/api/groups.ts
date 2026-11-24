import { ApiError, apiRequest, isRecord } from "@/lib/api/client";
import type { ContextWindowSource } from "@/lib/contextWindow";
import {
  type HeaderRule,
  isHeaderRule,
  isParamOverrideRule,
  type ParamOverrideRule,
} from "@/lib/upstreamRules";
import { isProtocolKind, type ProtocolKind } from "./protocols";

export type ModelTestMode = "direct" | "codex" | "claude";

export type RoutingStrategy = "round_robin" | "failover";
export type MatchRegexOperator = "and" | "or";
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
/** How a saved member joined: by hand, through match rules, or by placement. */
export type ModelGroupMemberSource = "manual" | "rule" | "placement";
export type ModelGroupItemPayload = {
  channel_id: string;
  credential_id: string;
  model_name: string;
  enabled: boolean;
  source?: ModelGroupMemberSource;
};
export type ModelGroupItem = ModelGroupItemPayload & {
  site_id: string | null;
  channel_name: string;
  protocol_config_id: string;
  protocol?: ProtocolKind | null;
  credential_name: string;
  credential_number: number;
  credential_mask: string;
  base_url: string;
  rate_multiplier: number | null;
  rate_source: "none" | "sub2api" | "newapi";
  state: ModelGroupItemState;
  reasons: ModelGroupItemReason[];
  sort_order: number;
  source: ModelGroupMemberSource;
  /** The channel model's own context window; null uses the group default. */
  context_window: number | null;
  context_window_source: ContextWindowSource | null;
};
export type ModelGroup = {
  id: string;
  name: string;
  client_protocols: ProtocolKind[];
  strategy: RoutingStrategy;
  route_group_id?: string;
  route_group_name?: string;
  /** The group name matches as a case-insensitive substring. */
  match_regex: string;
  match_regex_operator: MatchRegexOperator;
  param_override: ParamOverrideRule[];
  headers: HeaderRule[];
  fallback_group_ids?: string[];
  /** Default context window for members without their own value. */
  context_window: number | null;
  input_price_per_million: number;
  image_input_price_per_million: number;
  manual_override: boolean;
  output_price_per_million: number;
  cache_read_price_per_million: number;
  cache_write_price_per_million: number;
  image_price_per_image: number;
  pricing_mode: "free" | "tokens" | "non_tokens";
  items: ModelGroupItem[];
  /** Kept out of the group; automatic joining does not add them back. */
  excluded_items: ModelGroupItem[];
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
  credential_mask: string;
  rate_multiplier: number | null;
  rate_source: "none" | "sub2api" | "newapi";
  base_url: string;
  model_name: string;
  protocol_config_id: string;
  protocols: ProtocolKind[];
  items: ModelGroupCandidateSubitem[];
};
export type ModelGroupCandidatesPayload = {
  items: ModelGroupItemPayload[];
};
export type ModelGroupCandidatesResponse = {
  candidates: ModelGroupCandidateItem[];
  evaluated_items: ModelGroupItem[];
};
export type ModelGroupModelTestPayload = {
  channel_id: string;
  credential_id: string;
  model_name: string;
  test_mode: ModelTestMode;
  protocol?: ProtocolKind;
};
export type UnplacedModelProvider = {
  site_id: string;
  channel_name: string;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  credential_mask: string;
  base_url: string;
  protocols: ProtocolKind[];
};
/** A channel model name held back because its match key collides. */
export type UnplacedModel = {
  model_name: string;
  match_key: string;
  similar_group_ids: string[];
  similar_group_names: string[];
  similar_model_names: string[];
  providers: UnplacedModelProvider[];
};
export type UnplacedModelsResponse = { items: UnplacedModel[] };
export type ModelGroupPlacementRequest = {
  model_names: string[] | null;
  /** When set, join the names into this existing execution group. */
  group_id?: string;
};
export type ModelGroupMemberChange = {
  group_id: string;
  group_name: string;
  channel_id: string;
  channel_name: string;
  credential_id: string;
  credential_name: string;
  model_name: string;
  source: ModelGroupMemberSource;
};
export type ModelGroupPlacementResponse = {
  created: ModelGroup[];
  joined: ModelGroupMemberChange[];
  unplaced: UnplacedModel[];
};
/** Group-level outcome of one reconcile pass, in pipeline stage order. */
export type ModelGroupReconcileReport = {
  added: ModelGroupMemberChange[];
  removed: ModelGroupMemberChange[];
  created_groups: Array<{ id: string; name: string }>;
  pending: UnplacedModel[];
};
export type UnplacedModelRemovalRequest = {
  model_names: string[];
};
export type UnplacedModelRemovalResponse = {
  deleted: number;
};
export type ModelGroupMergeRequest = { target_group_id: string };

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
}

function isModelGroupItem(value: unknown): value is ModelGroupItem {
  if (!isRecord(value)) return false;
  return (
    typeof value.channel_id === "string" &&
    (value.site_id === null || typeof value.site_id === "string") &&
    typeof value.channel_name === "string" &&
    typeof value.credential_id === "string" &&
    typeof value.credential_name === "string" &&
    typeof value.credential_number === "number" &&
    typeof value.credential_mask === "string" &&
    typeof value.base_url === "string" &&
    typeof value.protocol_config_id === "string" &&
    (value.protocol === undefined ||
      value.protocol === null ||
      isProtocolKind(value.protocol)) &&
    typeof value.model_name === "string" &&
    typeof value.enabled === "boolean" &&
    typeof value.sort_order === "number" &&
    (typeof value.rate_multiplier === "number" ||
      value.rate_multiplier === null) &&
    (value.rate_source === "none" ||
      value.rate_source === "sub2api" ||
      value.rate_source === "newapi") &&
    (value.state === "ready" ||
      value.state === "disabled" ||
      value.state === "invalid" ||
      value.state === "unavailable") &&
    isStringArray(value.reasons) &&
    value.reasons.every(
      (reason) =>
        reason === "manual_disabled" ||
        reason === "channel_not_found" ||
        reason === "channel_disabled" ||
        reason === "credential_not_found" ||
        reason === "credential_disabled" ||
        reason === "model_not_found" ||
        reason === "model_disabled" ||
        reason === "model_upstream_missing",
    ) &&
    (value.source === "manual" ||
      value.source === "rule" ||
      value.source === "placement") &&
    (value.context_window === null ||
      typeof value.context_window === "number") &&
    (value.context_window_source === null ||
      value.context_window_source === "manual" ||
      value.context_window_source === "upstream")
  );
}

function isModelGroup(value: unknown): value is ModelGroup {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    isStringArray(value.client_protocols) &&
    value.client_protocols.every(isProtocolKind) &&
    (value.strategy === "round_robin" || value.strategy === "failover") &&
    (value.route_group_id === undefined ||
      typeof value.route_group_id === "string") &&
    (value.route_group_name === undefined ||
      typeof value.route_group_name === "string") &&
    typeof value.match_regex === "string" &&
    (value.match_regex_operator === "and" ||
      value.match_regex_operator === "or") &&
    Array.isArray(value.param_override) &&
    value.param_override.every(isParamOverrideRule) &&
    Array.isArray(value.headers) &&
    value.headers.every(isHeaderRule) &&
    (value.fallback_group_ids === undefined ||
      isStringArray(value.fallback_group_ids)) &&
    (value.context_window === null ||
      typeof value.context_window === "number") &&
    typeof value.input_price_per_million === "number" &&
    typeof value.image_input_price_per_million === "number" &&
    typeof value.output_price_per_million === "number" &&
    typeof value.cache_read_price_per_million === "number" &&
    typeof value.cache_write_price_per_million === "number" &&
    typeof value.image_price_per_image === "number" &&
    typeof value.manual_override === "boolean" &&
    (value.pricing_mode === "free" ||
      value.pricing_mode === "tokens" ||
      value.pricing_mode === "non_tokens") &&
    Array.isArray(value.items) &&
    value.items.every(isModelGroupItem) &&
    Array.isArray(value.excluded_items) &&
    value.excluded_items.every(isModelGroupItem)
  );
}

/** Loads the shared model-group list and rejects responses outside its API shape. */
export async function requestModelGroups(): Promise<ModelGroup[]> {
  const value = await apiRequest<unknown>("/admin/model-groups");
  if (!Array.isArray(value) || !value.every(isModelGroup)) {
    throw new ApiError("Invalid model groups response from API", 200);
  }
  return value;
}

export async function createModelGroup(body: string): Promise<string> {
  const group = await apiRequest<unknown>("/admin/model-groups", {
    method: "POST",
    body,
  });
  if (!isRecord(group) || typeof group.id !== "string" || !group.id.trim()) {
    throw new ApiError("Invalid created model group ID from API", 200);
  }
  return group.id;
}
