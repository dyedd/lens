import type { ContextWindowSource } from "@/lib/contextWindow";
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
  /** Library regex rules; when set they replace name matching for this group. */
  match_rule_ids: string[];
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
  prompt: string;
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
  /** Members whose model stayed missing upstream past the grace period. */
  retired: ModelGroupMemberChange[];
};
export type UnplacedModelRemovalRequest = {
  model_names: string[];
};
export type UnplacedModelRemovalResponse = {
  deleted: number;
};
export type ModelGroupMergeRequest = { target_group_id: string };
