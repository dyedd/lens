import type { HealthTier } from "@/lib/api/sites";
import { titleForLocale } from "@/lib/I18nContext";

export const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;
export const SEARCH_DEBOUNCE_MS = 300;

export type HealthMode = "model" | "channel";
export type HealthHours = "1" | "6" | "24";
export type Locale = "zh-CN" | "en-US";

export const HEALTH_HOURS = [
  { value: "1", zh: "1 小时", en: "1 hour" },
  { value: "6", zh: "6 小时", en: "6 hours" },
  { value: "24", zh: "24 小时", en: "24 hours" },
] as const;

const TIER_LABELS: Record<HealthTier, [string, string]> = {
  "no-data": ["无数据", "No data"],
  healthy: ["健康", "Healthy"],
  "mostly-healthy": ["基本健康", "Mostly healthy"],
  partial: ["部分失败", "Partial failures"],
  major: ["大量失败", "Major failures"],
  "all-failed": ["全部失败", "All failed"],
};

const BUCKET_TONE: Record<HealthTier, string> = {
  "no-data": "bg-muted",
  "all-failed": "bg-primary/15",
  major: "bg-primary/30",
  partial: "bg-primary/45",
  "mostly-healthy": "bg-primary/70",
  healthy: "bg-primary",
};

export function healthTierLabel(tier: HealthTier, locale: Locale) {
  return titleForLocale(locale, ...TIER_LABELS[tier]);
}

export function bucketTone(tier: HealthTier) {
  return BUCKET_TONE[tier];
}

export function formatSuccessRate(successCount: number, totalCount: number) {
  if (!totalCount) return "-";
  return `${((successCount / totalCount) * 100).toFixed(2)}%`;
}

export function hoursLabel(hours: HealthHours, locale: Locale) {
  const option = HEALTH_HOURS.find((item) => item.value === hours);
  if (!option) return hours;
  return locale === "zh-CN" ? option.zh : option.en;
}
