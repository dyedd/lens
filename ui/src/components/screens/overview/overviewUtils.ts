export type TimeRange = "-1" | "7" | "30" | "0";
export type PieMetric = "cost" | "requests" | "tokens";
export type HeatmapMetric = "requests" | "tokens" | "duration";
export type HeatmapPoint = {
  date: string;
  count: number;
  tokens: number;
  waitTimeMs: number;
};
export type StatTrendPoint = { label: string; value: number };

export const TIME_RANGE_OPTIONS = [
  { value: "-1", zhLabel: "今天", enLabel: "Today" },
  { value: "7", zhLabel: "近 7 天", enLabel: "Last 7 days" },
  { value: "30", zhLabel: "近 30 天", enLabel: "Last 30 days" },
  { value: "0", zhLabel: "全部", enLabel: "All time" },
] satisfies Array<{ value: TimeRange; zhLabel: string; enLabel: string }>;
export const PIE_METRIC_OPTIONS = [
  { value: "cost", zhLabel: "费用", enLabel: "Cost" },
  { value: "requests", zhLabel: "请求", enLabel: "Requests" },
  { value: "tokens", zhLabel: "Token", enLabel: "Tokens" },
] satisfies Array<{ value: PieMetric; zhLabel: string; enLabel: string }>;
export const CHART_COLORS = [
  "var(--chart-4)",
  "var(--chart-3)",
  "var(--chart-2)",
  "var(--chart-1)",
  "var(--chart-5)",
  "var(--primary)",
  "var(--muted-foreground)",
];

/** Convert a model name into a safe chart data key. */
export function safeKey(name: string) {
  return name.replace(/[^a-zA-Z0-9_-]/g, "_");
}
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
/** Format milliseconds using the most useful display unit. */
export function formatDuration(ms: number) {
  if (ms >= 3_600_000) return `${(ms / 3_600_000).toFixed(1)}h`;
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`;
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}
/** Format an overview trend bucket for chart axes. */
export function formatTrendLabel(bucket: string) {
  return bucket.length >= 10
    ? `${bucket.slice(8, 10)}:00`
    : `${bucket.slice(4, 6)}/${bucket.slice(6, 8)}`;
}
/** Normalize compact date keys to ISO date strings. */
export function parseDateKey(value: string) {
  return value.includes("-")
    ? value
    : value.length >= 8
      ? `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`
      : value;
}
/** Format a date key for sparkline labels. */
export function formatSparklineLabel(value: string) {
  const date = parseDateKey(value);
  return date.length >= 10 ? `${date.slice(5, 7)}/${date.slice(8, 10)}` : value;
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
/** Ensure a trend has enough points for chart rendering. */
export function normalizeTrend(points: StatTrendPoint[]) {
  return points.length >= 2
    ? points
    : [
        { label: "", value: 0 },
        { label: "", value: 0 },
      ];
}

/** Build localized labels for the selected model metric. */
export function getPieMetricLabels(metric: PieMetric, isChinese: boolean) {
  const label = isChinese
    ? metric === "cost"
      ? "费用"
      : metric === "requests"
        ? "请求"
        : "Token"
    : metric === "cost"
      ? "Cost"
      : metric === "requests"
        ? "Requests"
        : "Tokens";
  return {
    label,
    trendTitle: isChinese ? `${label}趋势` : `${label} trend`,
    cardDescription: isChinese
      ? `模型占比和${label}趋势`
      : `Model share and ${label.toLowerCase()} trend`,
  };
}
