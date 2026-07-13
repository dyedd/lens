import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupPayload,
  ModelGroupSyncFilterMode,
  ProtocolKind,
  RoutingStrategy,
  Site,
} from "@/lib/api";
import { protocolLabel } from "@/lib/protocols";
import { credentialDisplayLabel } from "./modelGroupFormatting";

export * from "./modelGroupFormatting";
export * from "./modelGroupMembers";

export type FormItem = {
  channel_id: string;
  channel_name: string;
  protocol?: ProtocolKind | null;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  model_name: string;
  enabled: boolean;
};

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
  subItems: FormItem[];
  enabled: boolean;
  invalid: boolean;
};

export type GroupDisplayMember = {
  key: string;
  model_name: string;
  credential_name: string;
  credential_number: number;
  channel_names: string[];
  protocols: ProtocolKind[];
  items: ModelGroup["items"];
  enabled: boolean;
  isRoutable: boolean;
  isUnavailable: boolean;
};

export type GroupSort =
  | "members-desc"
  | "enabled-desc"
  | "name-asc"
  | "name-desc";
export type CandidateSearchMode = Exclude<ModelGroupSyncFilterMode, "">;
export type MemberStatusFilter = "all" | "enabled" | "disabled";

export type GroupRow = ModelGroup & {
  member_count: number;
  enabled_member_count: number;
  unavailable_member_count: number;
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
  channelMap: Map<string, ProtocolMeta>,
  locale: "zh-CN" | "en-US",
) {
  const channel = channelMap.get(item.channel_id);
  const channelName = channel?.name || item.channel_name;
  const endpoint = item.base_url || channelEndpoint(channel);
  const credentialNumber =
    channel?.credential_number_by_id.get(item.credential_id) ??
    item.credential_number;
  const credentialLabel = credentialDisplayLabel(
    {
      credential_name: item.credential_name,
      credential_number: credentialNumber,
    },
    locale,
  );
  return `${item.model_name} ${channelName} ${protocolLabel(item.protocol, locale)} ${credentialLabel} ${item.credential_name} ${endpoint}`;
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
  channelMap: Map<string, ProtocolMeta>,
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
  const haystack = buildCandidateHaystack(item, channelMap, locale);
  return haystack.toLowerCase().includes(normalizedQuery.toLowerCase());
}

export function candidatePayloadItemProtocol(
  candidate: ModelGroupCandidateItem,
  channelId: string,
  channelMap?: Map<string, ProtocolMeta>,
): ProtocolKind | undefined {
  const channelProtocol = channelMap?.get(channelId)?.protocol;
  if (channelProtocol) {
    return channelProtocol;
  }
  const protocolEntry = Object.entries(candidate.protocol_channels).find(
    ([, candidateChannelId]) => candidateChannelId === channelId,
  );
  if (protocolEntry) {
    return protocolEntry[0] as ProtocolKind;
  }
  return channelId === candidate.channel_id ? candidate.protocol : undefined;
}

/** Convert candidate payload items into editable model group members. */
export function candidatePayloadToFormItems(
  candidate: ModelGroupCandidateItem,
  channelMap?: Map<string, ProtocolMeta>,
): FormItem[] {
  return candidate.items.map((payloadItem) => {
    const channel = channelMap?.get(payloadItem.channel_id);
    const channelName = channel?.name || candidate.channel_name;
    return {
      channel_id: payloadItem.channel_id,
      channel_name: channelName,
      protocol: candidatePayloadItemProtocol(
        candidate,
        payloadItem.channel_id,
        channelMap,
      ),
      credential_id: payloadItem.credential_id,
      credential_name: candidate.credential_name,
      credential_number:
        channel?.credential_number_by_id.get(payloadItem.credential_id) ??
        candidate.credential_number,
      model_name: payloadItem.model_name,
      enabled: true,
    };
  });
}

export type ProtocolMeta = {
  id: string;
  site_id: string;
  name: string;
  base_url: string;
  protocol: ProtocolKind;
  enabled: boolean;
  credential_enabled_by_id: Map<string, boolean>;
  credential_number_by_id: Map<string, number>;
  model_enabled_by_key: Map<string, boolean>;
};

export function channelEndpoint(channel?: ProtocolMeta) {
  if (!channel) return "";
  return channel.base_url || "";
}

/** Resolve a site's base URL by identifier. */
export function protocolBaseUrl(site: Site, baseUrlId: string) {
  const bound = site.base_urls.find((item) => item.id === baseUrlId);
  return bound?.url || "";
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
        channel_name: item.channel_name,
        protocol: item.protocol,
        credential_id: item.credential_id,
        credential_name: item.credential_name,
        credential_number: item.credential_number,
        model_name: item.model_name,
        enabled: item.enabled,
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
