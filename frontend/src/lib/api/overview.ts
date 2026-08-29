export type OverviewSummaryMetric = { value: number; delta: number };
export type OverviewSummary = {
  request_count: OverviewSummaryMetric;
  wait_time_ms: OverviewSummaryMetric;
  total_tokens: OverviewSummaryMetric;
  total_cost_usd: OverviewSummaryMetric;
  input_tokens: OverviewSummaryMetric;
  cache_read_input_tokens: OverviewSummaryMetric;
  cache_write_input_tokens: OverviewSummaryMetric;
  input_cost_usd: OverviewSummaryMetric;
  output_tokens: OverviewSummaryMetric;
  output_cost_usd: OverviewSummaryMetric;
};
export type OverviewDailyPoint = {
  date: string;
  request_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  wait_time_ms: number;
  successful_requests: number;
  failed_requests: number;
};
export type OverviewModelMetricPoint = {
  model: string;
  requests: number;
  total_tokens: number;
  total_cost_usd: number;
};
export type OverviewModelTrendPoint = {
  date: string;
  model: string;
  value: number;
};
export type OverviewModelAnalytics = {
  distribution: OverviewModelMetricPoint[];
  trend: OverviewModelTrendPoint[];
  available_models: string[];
};
