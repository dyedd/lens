import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupItemReason,
  ModelGroupItemState,
  ModelGroupSyncFilterMode,
  RoutingStrategy,
} from "@/lib/api/groups";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { HeaderItem } from "../settings/upstreamHeaderConfig";

export type FormItem = {
  channel_id: string;
  site_id: string | null;
  protocol_config_id: string;
  channel_name: string;
  protocol?: ProtocolKind | null;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  rate_multiplier: number | null;
  rate_source: "none" | "sub2api" | "newapi";
  model_name: string;
  enabled: boolean;
  state: ModelGroupItemState | null;
  reasons: ModelGroupItemReason[];
};

export type EvaluatedFormItem = FormItem;

export type FormState = {
  name: string;
  strategy: RoutingStrategy;
  route_group_id: string;
  sync_filter_mode: ModelGroupSyncFilterMode;
  sync_filter_query: string;
  param_override: string;
  headers: HeaderItem[];
  input_price_per_million: string;
  output_price_per_million: string;
  cache_read_price_per_million: string;
  cache_write_price_per_million: string;
  image_price_per_image: string;
  pricing_mode: "tokens" | "non_tokens";
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
  rate_multiplier: number | null;
  rate_source: "none" | "sub2api" | "newapi";
  protocols: ProtocolKind[];
  subItems: EvaluatedFormItem[];
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

export type GroupDisplayChannel = {
  key: string;
  channel_id: string;
  channel_name: string;
  members: GroupDisplayMember[];
};

export type GroupDisplayMember = {
  key: string;
  model_name: string;
  credential_name: string;
  credential_number: number;
  channel_names: string[];
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
export type CandidateSearchMode = Exclude<ModelGroupSyncFilterMode, "">;
export type MemberStatusFilter = "all" | "enabled" | "disabled" | "problem";

export type GroupRow = ModelGroup & {
  member_count: number;
  enabled_member_count: number;
  problem_member_count: number;
  channel_summary: string;
  channel_names: string[];
  display_members: GroupDisplayMember[];
  display_channels: GroupDisplayChannel[];
  is_route_group: boolean;
};

export const EMPTY_FORM: FormState = {
  name: "",
  strategy: "round_robin",
  route_group_id: "",
  sync_filter_mode: "",
  sync_filter_query: "",
  param_override: "",
  headers: [{ key: "", value: "" }],
  input_price_per_million: "0",
  output_price_per_million: "0",
  cache_read_price_per_million: "0",
  cache_write_price_per_million: "0",
  image_price_per_image: "0",
  pricing_mode: "tokens",
  items: [],
};
