export type TimeRange = "-1" | "7" | "30" | "0";
export type AnalysisMetric =
  | "cost"
  | "requests"
  | "tokens"
  | "cache"
  | "duration";
export type AttributionDimension = "model" | "channel";
export type HeatmapPoint = {
  date: string;
  count: number;
};
export function requestLogsHref(
  timeRange: TimeRange,
  filters: {
    model?: string;
    channel?: string;
    status?: "success" | "failed";
  } = {},
) {
  const params = new URLSearchParams({ days: timeRange });
  if (filters.status) params.set("status", filters.status);
  if (filters.model !== undefined) params.set("upstream_model", filters.model);
  if (filters.channel !== undefined)
    params.set("channel", filters.channel || "n/a");
  return `/requests?${params}`;
}
export const TIME_RANGE_OPTIONS = [
  { value: "-1", zhLabel: "今天", enLabel: "Today" },
  { value: "7", zhLabel: "近 7 天", enLabel: "Last 7 days" },
  { value: "30", zhLabel: "近 30 天", enLabel: "Last 30 days" },
  { value: "0", zhLabel: "全部", enLabel: "All time" },
] satisfies Array<{ value: TimeRange; zhLabel: string; enLabel: string }>;
export const CHART_COLORS = [
  "var(--chart-4)",
  "var(--chart-3)",
  "var(--chart-2)",
  "var(--chart-1)",
  "var(--chart-5)",
  "var(--primary)",
  "var(--muted-foreground)",
];

/** Format a number using compact dashboard notation. */
export function formatCompact(value: number, digits = 1) {
  if (value >= 1_000_000_000)
    return `${(value / 1_000_000_000).toFixed(digits)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(digits)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(digits)}K`;
  return String(Math.round(value));
}
/** Format a dollar value for overview cards and charts. */
export function formatMoney(value: number) {
  return value >= 1000
    ? `$${formatCompact(value, 2)}`
    : `$${value.toFixed(value >= 100 ? 0 : 2)}`;
}
export function formatDuration(ms: number, isChinese = false) {
  const units = [
    { size: 86_400_000, label: isChinese ? "天" : "d" },
    { size: 3_600_000, label: isChinese ? "小时" : "h" },
    { size: 60_000, label: isChinese ? "分钟" : "m" },
    { size: 1000, label: isChinese ? "秒" : "s" },
  ];
  const first = units.findIndex((unit) => ms >= unit.size);
  if (first >= 0 && first < units.length - 1) {
    const unit = units[first];
    const next = units[first + 1];
    const whole = Math.floor(ms / unit.size);
    const remainder = Math.floor((ms % unit.size) / next.size);
    return `${whole}${unit.label}${remainder ? ` ${remainder}${next.label}` : ""}`;
  }
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}${isChinese ? "秒" : "s"}`;
  return `${Math.round(ms)}${isChinese ? "毫秒" : "ms"}`;
}
/** Convert an attribution rate from 0..1 to a display percentage. */
export function formatRate(rate: number | null) {
  return rate === null ? "—" : `${(rate * 100).toFixed(1)}%`;
}
/** Format an overview trend bucket for chart axes. */
export function formatTrendLabel(bucket: string) {
  return bucket.length >= 10
    ? `${bucket.slice(8, 10)}:00`
    : `${bucket.slice(4, 6)}/${bucket.slice(6, 8)}`;
}
/** Parse compact date keys into ISO date strings. */
export function parseDateKey(value: string) {
  return value.includes("-")
    ? value
    : value.length >= 8
      ? `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`
      : value;
}
/** Convert a local date to an ISO date key. */
export function toLocalDateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
/** Return a new date offset by the requested day count. */
export function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}
/** Find the Monday that begins a heatmap week. */
export function startOfHeatmapWeek(date: Date) {
  const day = date.getDay();
  return addDays(date, day === 0 ? -6 : 1 - day);
}
