import type { ModelGroupCandidateItem, RoutingStrategy } from "@/lib/api";
import { isGeneratedCredentialName } from "@/lib/utils";
import type { FoldedMember, FormItem, GroupRow } from "./modelGroupUtils";

export const STRATEGY_OPTIONS: Array<{
  value: RoutingStrategy;
  zh: string;
  en: string;
}> = [
  { value: "round_robin", zh: "轮询", en: "Round Robin" },
  { value: "failover", zh: "故障转移", en: "Failover" },
];

export function credentialDisplayLabel(
  item: Pick<
    FormItem | ModelGroupCandidateItem,
    "credential_name" | "credential_number"
  >,
  locale: "zh-CN" | "en-US",
) {
  const name = item.credential_name.trim();
  if (name && !isGeneratedCredentialName(name)) {
    return name;
  }
  const number = item.credential_number > 0 ? item.credential_number : 1;
  return locale === "zh-CN" ? `密钥 ${number}` : `Key ${number}`;
}

/** Format a localized credential number label. */
export function credentialNumberLabel(
  item: Pick<FormItem | ModelGroupCandidateItem, "credential_number">,
  locale: "zh-CN" | "en-US",
) {
  const number = item.credential_number > 0 ? item.credential_number : 1;
  return locale === "zh-CN" ? `密钥 ${number}` : `Key ${number}`;
}

/** Format the source channel label for a folded member. */
export function foldedMemberSourceLabel(
  member: FoldedMember,
  locale: "zh-CN" | "en-US",
) {
  const channelNames = Array.from(
    new Set(member.subItems.map((item) => item.channel_name).filter(Boolean)),
  );
  const credentialLabel = credentialNumberLabel(member, locale);
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
export function isGroupEnabled(group: Pick<GroupRow, "enabled_member_count">) {
  return group.enabled_member_count > 0;
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
