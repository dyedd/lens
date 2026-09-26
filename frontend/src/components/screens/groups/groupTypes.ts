import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupItemReason,
  ModelGroupItemState,
  RoutingStrategy,
} from "@/lib/api/groups";
import type { ProtocolKind } from "@/lib/api/protocols";
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
  /** Joined through the group's live match rules rather than saved explicitly. */
  matched_by_rule: boolean;
  state: ModelGroupItemState | null;
  reasons: ModelGroupItemReason[];
};

export type EvaluatedFormItem = FormItem;

export type FormState = {
  name: string;
  strategy: RoutingStrategy;
  route_group_id: string;
  match_models: string[];
  match_regex: string;
  param_override: ParamOverrideRuleDraft[];
  headers: HeaderRuleDraft[];
  fallback_group_ids: string[];
  items: FormItem[];
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
  protocols: ProtocolKind[];
  subItems: EvaluatedFormItem[];
  is_rule_member: boolean;
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
  matched_by_rule: boolean;
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
  match_models: [],
  match_regex: "",
  param_override: [{ path: "", action: "set", value: "" }],
  headers: [{ key: "", value: "", action: "override" }],
  fallback_group_ids: [],
  items: [],
};
