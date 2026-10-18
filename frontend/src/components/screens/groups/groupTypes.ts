import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupItemReason,
  ModelGroupItemState,
  ModelGroupMemberSource,
  RoutingStrategy,
} from "@/lib/api/groups";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { ContextWindowSource } from "@/lib/contextWindow";
import type {
  HeaderRuleDraft,
  ParamOverrideRuleDraft,
} from "@/lib/upstreamRules";

export type FormItem = {
  channel_id: string;
  site_id: string | null;
  protocol_config_id: string;
  channel_name: string;
  protocol?: ProtocolKind | null;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  credential_mask: string;
  base_url: string;
  rate_multiplier: number | null;
  rate_source: "none" | "sub2api" | "newapi";
  model_name: string;
  enabled: boolean;
  source: ModelGroupMemberSource;
  state: ModelGroupItemState | null;
  reasons: ModelGroupItemReason[];
  /** The channel model's own context window; null uses the group default. */
  context_window: number | null;
  context_window_source: ContextWindowSource | null;
};

export type EvaluatedFormItem = FormItem;

export type FormState = {
  name: string;
  strategy: RoutingStrategy;
  route_group_id: string;
  /** Library regex rules; when set they replace name matching for this group. */
  match_rule_ids: string[];
  param_override: ParamOverrideRuleDraft[];
  headers: HeaderRuleDraft[];
  fallback_group_ids: string[];
  /** Default context window text, e.g. "1M"; empty means unknown. */
  context_window: string;
  items: FormItem[];
  /** Members kept out so match rules and placement do not add them back. */
  excluded_items: FormItem[];
};

export type CandidateChannelGroup = {
  key: string;
  site_id: string;
  channel_name: string;
  candidates: ModelGroupCandidateItem[];
};

export type FoldedMember = {
  key: string;
  protocolConfigId: string;
  siteId: string | null;
  channel_id: string;
  channel_name: string;
  model_name: string;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  credential_mask: string;
  base_url: string;
  rate_multiplier: number | null;
  rate_source: "none" | "sub2api" | "newapi";
  context_window: number | null;
  context_window_source: ContextWindowSource | null;
  protocols: ProtocolKind[];
  subItems: EvaluatedFormItem[];
  /** Shared source of every sub item; mixed sources count as manual. */
  source: ModelGroupMemberSource;
  enabled_item_count: number;
  disabled_item_count: number;
  ready_item_count: number;
  invalid_item_count: number;
  unavailable_item_count: number;
  pending_item_count: number;
};

export type ChannelMemberGroup = {
  key: string;
  channel_id: string;
  channel_name: string;
  priority: number;
  members: Array<{ member: FoldedMember; index: number }>;
};

export type GroupDisplayMember = {
  key: string;
  model_name: string;
  channel_name: string;
  credential_name: string;
  credential_number: number;
  credential_mask: string;
  base_url: string;
  source: ModelGroupMemberSource;
  protocols: ProtocolKind[];
  items: ModelGroup["items"];
  enabled_item_count: number;
  disabled_item_count: number;
  ready_item_count: number;
  invalid_item_count: number;
  unavailable_item_count: number;
};

export type GroupSort =
  | "members-desc"
  | "enabled-desc"
  | "name-asc"
  | "name-desc";
export type MemberStatusFilter = "all" | "enabled" | "disabled" | "problem";

export type SimilarGroupView = { id: string; name: string };

export type GroupRow = ModelGroup & {
  member_count: number;
  enabled_member_count: number;
  problem_member_count: number;
  site_count: number;
  credential_count: number;
  channel_names: string[];
  display_members: GroupDisplayMember[];
  /** Other execution groups whose name or match models share a match key. */
  similar_groups: SimilarGroupView[];
  is_route_group: boolean;
};

export const EMPTY_FORM: FormState = {
  name: "",
  strategy: "failover",
  route_group_id: "",
  match_rule_ids: [],
  param_override: [{ path: "", action: "set", value: "" }],
  headers: [{ key: "", value: "", action: "override" }],
  fallback_group_ids: [],
  context_window: "",
  items: [],
  excluded_items: [],
};
