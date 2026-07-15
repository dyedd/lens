import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupItemReason,
  ModelGroupItemState,
  RoutingStrategy,
} from "@/lib/api";
import { formatCredentialDisplayName } from "@/lib/utils";
import type { FoldedMember, FormItem } from "./modelGroupUtils";

export const STRATEGY_OPTIONS: Array<{
  value: RoutingStrategy;
  zh: string;
  en: string;
}> = [
  { value: "round_robin", zh: "轮询", en: "Round Robin" },
  { value: "failover", zh: "故障转移", en: "Failover" },
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
    protocol_unreachable: {
      zh: "无法服务所选协议",
      en: "Cannot serve selected protocols",
    },
    channel_disabled: { zh: "渠道不可用", en: "Channel unavailable" },
    credential_not_found: { zh: "密钥不存在", en: "Key not found" },
    credential_disabled: { zh: "密钥不可用", en: "Key unavailable" },
    model_not_found: { zh: "模型不存在", en: "Model not found" },
    model_disabled: { zh: "模型不可用", en: "Model unavailable" },
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

/** Build the stable identity key for a model group member. */
export function itemKey(
  item: Pick<FormItem, "channel_id" | "credential_id" | "model_name">,
) {
  return `${item.channel_id}::${item.credential_id}::${item.model_name}`;
}

/** Return whether a group has at least one enabled member. */
export function isGroupEnabled(group: Pick<ModelGroup, "items">) {
  return group.items.some((item) => item.enabled);
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
