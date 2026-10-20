import type {
  ModelGroup,
  ModelGroupItemReason,
  ModelGroupItemState,
  ModelGroupMemberSource,
  RoutingStrategy,
} from "@/lib/api/groups";
import { formatCredentialDisplayName } from "@/lib/credentialLabels";
import type { FormItem, GroupDisplayMember } from "./groupTypes";

export const STRATEGY_OPTIONS: Array<{
  value: RoutingStrategy;
  zh: string;
  en: string;
}> = [
  { value: "failover", zh: "故障切换", en: "Failover" },
  { value: "round_robin", zh: "平滑轮询", en: "Round Robin" },
];

/** Return the localized label for a routing strategy. */
export function strategyLabel(
  strategy: RoutingStrategy,
  locale: "zh-CN" | "en-US",
) {
  const option = STRATEGY_OPTIONS.find((item) => item.value === strategy);
  return option ? (locale === "zh-CN" ? option.zh : option.en) : strategy;
}

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
    credential_not_found: { zh: "访问凭证不存在", en: "Credential not found" },
    credential_disabled: { zh: "访问凭证已停用", en: "Credential unavailable" },
    model_not_found: { zh: "模型不存在", en: "Model not found" },
    model_disabled: { zh: "模型已停用", en: "Model disabled" },
    model_upstream_missing: {
      zh: "上游未提供，保留待审",
      en: "Missing upstream, review needed",
    },
  };
  return labels[reason][locale === "zh-CN" ? "zh" : "en"];
}

type CredentialIdentity = {
  channel_name: string;
  credential_name: string;
  credential_number: number;
  credential_mask: string;
  base_url: string;
};

export function credentialDisplayLabel(
  item: Pick<CredentialIdentity, "credential_name" | "credential_number">,
  locale: "zh-CN" | "en-US",
) {
  return formatCredentialDisplayName(
    item.credential_name,
    item.credential_number,
    locale,
  );
}

/** Return the host of an upstream URL, or the raw value when unparsable. */
function formatUrlHost(url: string) {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

/** Format the full key identity: site · key remark · mask · URL host. */
export function formatCredentialIdentity(
  item: CredentialIdentity,
  locale: "zh-CN" | "en-US",
  { includeSite = true }: { includeSite?: boolean } = {},
) {
  return [
    includeSite ? item.channel_name : "",
    credentialDisplayLabel(item, locale),
    item.credential_mask,
    item.base_url ? formatUrlHost(item.base_url) : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

/** Format how a member joined its group. */
export function formatMemberSource(
  source: ModelGroupMemberSource,
  locale: "zh-CN" | "en-US",
) {
  // "rule" only appears in rows and backups written before name-based joining.
  if (source === "rule" || source === "placement") {
    return locale === "zh-CN" ? "自动" : "Auto";
  }
  return locale === "zh-CN" ? "手动" : "Manual";
}

/** Format a model price for compact display. */
export function formatMoney(value: number) {
  if (value === 0) return "0";
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: value >= 1 ? 2 : 0,
    maximumFractionDigits: 4,
  }).format(value);
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

/** Build the backend's collision key: lowercase letters and digits only. */
export function buildModelMatchKey(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]/g, "");
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
    let member = memberMap.get(key);
    if (!member) {
      member = {
        key,
        model_name: item.model_name,
        channel_name: item.channel_name || item.channel_id,
        credential_name: item.credential_name,
        credential_number: item.credential_number,
        credential_mask: item.credential_mask,
        base_url: item.base_url,
        source: item.source,
        items: [],
        enabled_item_count: 0,
        disabled_item_count: 0,
        ready_item_count: 0,
        invalid_item_count: 0,
        unavailable_item_count: 0,
      };
      memberMap.set(key, member);
    }

    member.items.push(item);
    if (member.source !== item.source) member.source = "manual";
    if (item.enabled) member.enabled_item_count += 1;
    else member.disabled_item_count += 1;
    if (item.state === "ready") member.ready_item_count += 1;
    if (item.state === "invalid") member.invalid_item_count += 1;
    if (item.state === "unavailable") member.unavailable_item_count += 1;
  }

  return Array.from(memberMap.values());
}
