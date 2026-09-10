import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupItemReason,
  ModelGroupItemState,
  RoutingStrategy,
} from "@/lib/api/groups";
import { formatCredentialDisplayName } from "@/lib/credentialLabels";
import type { FoldedMember, FormItem } from "./groupTypes";

export const STRATEGY_OPTIONS: Array<{
  value: RoutingStrategy;
  zh: string;
  en: string;
}> = [
  { value: "failover", zh: "故障转移", en: "Failover" },
  { value: "round_robin", zh: "轮询", en: "Round Robin" },
];

export function modelGroupReasonsForState(
  items: Array<{
    state: ModelGroupItemState | null;
    reasons: ModelGroupItemReason[];
  }>,
  state: ModelGroupItemState,
) {
  return Array.from(
    new Set(
      items
        .filter((item) => item.state === state)
        .flatMap((item) => item.reasons),
    ),
  );
}

export function modelGroupItemReasonLabel(
  reason: ModelGroupItemReason,
  locale: "zh-CN" | "en-US",
) {
  const labels: Record<ModelGroupItemReason, { zh: string; en: string }> = {
    manual_disabled: { zh: "成员已关闭", en: "Member disabled" },
    channel_not_found: { zh: "渠道不存在", en: "Channel not found" },
    channel_disabled: { zh: "渠道已停用", en: "Channel disabled" },
    credential_not_found: { zh: "密钥不存在", en: "Key not found" },
    credential_disabled: { zh: "密钥不可用", en: "Key unavailable" },
    model_not_found: { zh: "模型不存在", en: "Model not found" },
    model_disabled: { zh: "模型已停用", en: "Model disabled" },
  };
  return labels[reason][locale === "zh-CN" ? "zh" : "en"];
}

export function credentialDisplayLabel(
  item: Pick<
    FormItem | ModelGroupCandidateItem,
    "credential_name" | "credential_number"
  >,
  locale: "zh-CN" | "en-US",
) {
  return formatCredentialDisplayName(
    item.credential_name,
    item.credential_number,
    locale,
  );
}

/** Format the source channel label for a folded member. */
export function foldedMemberSourceLabel(
  member: FoldedMember,
  locale: "zh-CN" | "en-US",
) {
  const channelNames = Array.from(
    new Set(member.subItems.map((item) => item.channel_name).filter(Boolean)),
  );
  const credentialLabel = credentialDisplayLabel(member, locale);
  return [...channelNames, credentialLabel].join(" · ");
}

/** Format a model price for compact display. */
export function formatMoney(value: number) {
  if (value === 0) return "0";
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: value >= 1 ? 2 : 0,
    maximumFractionDigits: 4,
  }).format(value);
}

/** Return the localized label for a token price metric. */
export function metricLabel(
  key: "input" | "output" | "cache_read" | "cache_write",
  locale: "zh-CN" | "en-US",
) {
  const labels: Record<
    "input" | "output" | "cache_read" | "cache_write",
    { zh: string; en: string }
  > = {
    input: { zh: "输入", en: "Input" },
    output: { zh: "输出", en: "Output" },
    cache_read: { zh: "缓存读取", en: "Cache Read" },
    cache_write: { zh: "缓存写入", en: "Cache Write" },
  };

  return labels[key][locale === "zh-CN" ? "zh" : "en"];
}

/** Return an error message with a caller-provided fallback. */
export function modelGroupErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

/** Return whether a group has at least one currently usable member. */
export function isGroupEnabled(group: Pick<ModelGroup, "items">) {
  return group.items.some((item) => item.state === "ready");
}

/** Return a copy with one item moved between valid indexes. */
export function moveItems<T>(items: T[], fromIndex: number, toIndex: number) {
  if (
    fromIndex === toIndex ||
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= items.length ||
    toIndex >= items.length
  ) {
    return items;
  }
  const nextItems = items.slice();
  const [target] = nextItems.splice(fromIndex, 1);
  nextItems.splice(toIndex, 0, target);
  return nextItems;
}

import { protocolLabel } from "@/lib/protocols";
import type {
  CandidateSearchMode,
  GroupDisplayChannel,
  GroupDisplayMember,
} from "./groupTypes";

function candidateSearchText(
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
  const trimmedValue = value.trim();
  const pattern = trimmedValue.startsWith("(?i)")
    ? trimmedValue.slice(4)
    : trimmedValue;
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
  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    return true;
  }
  if (mode === "regex") {
    const regex = compileCandidateRegex(trimmedQuery);
    if (!regex) {
      return false;
    }
    return regex.test(item.model_name);
  }
  return candidateSearchText(item, locale)
    .toLowerCase()
    .includes(trimmedQuery.toLowerCase());
}

/** Build the stable identity key for a model group member. */
export function modelGroupItemKey(
  item: Pick<FormItem, "channel_id" | "credential_id" | "model_name">,
) {
  return `${item.channel_id}::${item.credential_id}::${item.model_name}`;
}

/** Build the stable key used to fold equivalent model members. */
export function modelFoldKey(
  protocolConfigId: string,
  credentialId: string,
  modelName: string,
): string {
  return `${protocolConfigId}::${credentialId}::${modelName}`;
}

/** Build the shared channel identity used by failover ordering. */
export function modelGroupChannelKey(
  siteId: string | null,
  channelId: string,
): string {
  return siteId ? `site:${siteId}` : `channel:${channelId}`;
}

/** Fold stored group items into display members with availability state. */
export function buildGroupDisplayMembers(
  items: ModelGroup["items"],
): GroupDisplayMember[] {
  const memberMap = new Map<string, GroupDisplayMember>();

  for (const item of items) {
    const key = modelFoldKey(
      item.protocol_config_id,
      item.credential_id,
      item.model_name,
    );
    const channelName = item.channel_name || item.channel_id;

    if (!memberMap.has(key)) {
      memberMap.set(key, {
        key,
        model_name: item.model_name,
        credential_name: item.credential_name,
        credential_number: item.credential_number,
        channel_names: [],
        protocols: [],
        items: [],
        enabled_item_count: 0,
        disabled_item_count: 0,
        ready_item_count: 0,
        invalid_item_count: 0,
        unavailable_item_count: 0,
      });
    }

    const member = memberMap.get(key)!;
    member.items.push(item);
    if (item.enabled) member.enabled_item_count += 1;
    else member.disabled_item_count += 1;
    if (item.state === "ready") member.ready_item_count += 1;
    if (item.state === "invalid") member.invalid_item_count += 1;
    if (item.state === "unavailable") member.unavailable_item_count += 1;
    if (channelName && !member.channel_names.includes(channelName)) {
      member.channel_names.push(channelName);
    }
    if (item.protocol && !member.protocols.includes(item.protocol)) {
      member.protocols.push(item.protocol);
    }
  }

  return Array.from(memberMap.values());
}

/** Group display members by their channel while preserving first appearance. */
export function buildGroupDisplayChannels(
  members: GroupDisplayMember[],
): GroupDisplayChannel[] {
  const channels = new Map<string, GroupDisplayChannel>();
  for (const member of members) {
    const firstItem = member.items[0];
    if (!firstItem) continue;
    const key = modelGroupChannelKey(firstItem.site_id, firstItem.channel_id);
    let channel = channels.get(key);
    if (!channel) {
      channel = {
        key,
        channel_id: firstItem.channel_id,
        channel_name: firstItem.channel_name,
        members: [],
      };
      channels.set(key, channel);
    }
    channel.members.push(member);
  }
  return Array.from(channels.values());
}
