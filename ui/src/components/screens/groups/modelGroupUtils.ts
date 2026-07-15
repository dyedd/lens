import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupItemReason,
  ModelGroupItemState,
  ModelGroupPayload,
  ModelGroupSyncFilterMode,
  ProtocolKind,
  RoutingStrategy,
} from "@/lib/api";
import { protocolLabel } from "@/lib/protocols";
import { credentialDisplayLabel } from "./modelGroupFormatting";

export * from "./modelGroupFormatting";
export * from "./modelGroupMembers";

export type FormItem = {
  channel_id: string;
  protocol_config_id: string;
  channel_name: string;
  protocol?: ProtocolKind | null;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  model_name: string;
  enabled: boolean;
  state: ModelGroupItemState | null;
  reasons: ModelGroupItemReason[];
};

export type EvaluatedFormItem = FormItem;

export type FormState = {
  name: string;
  protocols: ProtocolKind[];
  strategy: RoutingStrategy;
  route_group_id: string;
  sync_filter_mode: ModelGroupSyncFilterMode;
  sync_filter_query: string;
  input_price_per_million: string;
  output_price_per_million: string;
  cache_read_price_per_million: string;
  cache_write_price_per_million: string;
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
  model_name: string;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  protocols: ProtocolKind[];
  subItems: EvaluatedFormItem[];
  enabled_item_count: number;
  disabled_item_count: number;
  ready_item_count: number;
  invalid_item_count: number;
  unavailable_item_count: number;
  pending_item_count: number;
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
  is_route_group: boolean;
};

export const EMPTY_FORM: FormState = {
  name: "",
  protocols: ["openai_chat"],
  strategy: "round_robin",
  route_group_id: "",
  sync_filter_mode: "",
  sync_filter_query: "",
  input_price_per_million: "0",
  output_price_per_million: "0",
  cache_read_price_per_million: "0",
  cache_write_price_per_million: "0",
  items: [],
};

export function buildCandidateHaystack(
  item: ModelGroupCandidateItem,
  locale: "zh-CN" | "en-US",
) {
  const credentialLabel = credentialDisplayLabel(
    {
      credential_name: item.credential_name,
      credential_number: item.credential_number,
    },
    locale,
  );
  const protocols = item.protocols
    .map((protocol) => protocolLabel(protocol, locale))
    .join(" ");
  return `${item.model_name} ${item.channel_name} ${protocols} ${credentialLabel} ${item.credential_name} ${item.base_url}`;
}

/** Compile a case-insensitive candidate search pattern when valid. */
export function compileCandidateRegex(value: string) {
  const normalizedValue = value.trim();
  const pattern = normalizedValue.startsWith("(?i)")
    ? normalizedValue.slice(4)
    : normalizedValue;
  try {
    return new RegExp(pattern, "i");
  } catch {
    return null;
  }
}

/** Return whether a candidate matches the selected search mode and query. */
export function matchesCandidateSearch(
  item: ModelGroupCandidateItem,
  mode: CandidateSearchMode,
  query: string,
  locale: "zh-CN" | "en-US",
) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    return true;
  }
  if (mode === "regex") {
    const regex = compileCandidateRegex(normalizedQuery);
    if (!regex) {
      return false;
    }
    return regex.test(item.model_name);
  }
  const haystack = buildCandidateHaystack(item, locale);
  return haystack.toLowerCase().includes(normalizedQuery.toLowerCase());
}

/** Convert candidate payload items into editable model group members. */
export function candidatePayloadToFormItems(
  candidate: ModelGroupCandidateItem,
): FormItem[] {
  return candidate.items.map((payloadItem) => {
    return {
      channel_id: payloadItem.channel_id,
      protocol_config_id: payloadItem.protocol_config_id,
      channel_name: candidate.channel_name,
      protocol: payloadItem.protocol,
      credential_id: payloadItem.credential_id,
      credential_name: candidate.credential_name,
      credential_number: candidate.credential_number,
      model_name: payloadItem.model_name,
      enabled: true,
      state: null,
      reasons: [],
    };
  });
}

/** Convert a persisted model group into editor form state. */
export function toForm(group: ModelGroup): FormState {
  return {
    name: group.name,
    protocols: group.protocols,
    strategy: group.strategy,
    route_group_id: group.route_group_id ?? "",
    sync_filter_mode: group.sync_filter_mode,
    sync_filter_query: group.sync_filter_query,
    input_price_per_million: String(group.input_price_per_million),
    output_price_per_million: String(group.output_price_per_million),
    cache_read_price_per_million: String(group.cache_read_price_per_million),
    cache_write_price_per_million: String(group.cache_write_price_per_million),
    items: group.items
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((item) => ({
        channel_id: item.channel_id,
        protocol_config_id: item.protocol_config_id,
        channel_name: item.channel_name,
        protocol: item.protocol,
        credential_id: item.credential_id,
        credential_name: item.credential_name,
        credential_number: item.credential_number,
        model_name: item.model_name,
        enabled: item.enabled,
        state: item.state,
        reasons: item.reasons,
      })),
  };
}

/** Normalize model group form state into an API payload. */
export function toPayload(form: FormState): ModelGroupPayload {
  return {
    name: form.name.trim(),
    protocols: form.protocols,
    strategy: form.strategy,
    route_group_id: form.route_group_id.trim(),
    sync_filter_mode:
      form.route_group_id.trim() || !form.sync_filter_query.trim()
        ? ""
        : form.sync_filter_mode,
    sync_filter_query: form.route_group_id.trim()
      ? ""
      : form.sync_filter_query.trim(),
    items: form.items.map((item) => ({
      channel_id: item.channel_id,
      credential_id: item.credential_id,
      model_name: item.model_name,
      enabled: item.enabled,
    })),
  };
}
