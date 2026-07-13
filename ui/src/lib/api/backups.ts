import { apiFetch, apiRequest } from "./client";
import type { CronjobScheduleType } from "./cronjobs";
import type { ModelGroup } from "./groups";
import type { ModelPriceItem } from "./modelPrices";
import type { ProtocolKind } from "./protocols";
import type { RequestLogAttempt, RequestLogLifecycleStatus } from "./requests";
import type { SettingItem } from "./settings";
import type { Site } from "./sites";

export type ConfigBackupImportedStatsTotal = {
  input_token: number;
  output_token: number;
  input_cost: number;
  output_cost: number;
  wait_time: number;
  request_success: number;
  request_failed: number;
};
export type ConfigBackupImportedStatsDaily = ConfigBackupImportedStatsTotal & {
  date: string;
};
export type ConfigBackupRequestLogDailyStat = {
  date: string;
  request_count: number;
  successful_requests: number;
  failed_requests: number;
  wait_time_ms: number;
  input_tokens: number;
  cache_read_input_tokens: number;
  cache_write_input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_cost_usd: number;
  output_cost_usd: number;
  total_cost_usd: number;
};
export type ConfigBackupOverviewModelDailyStat = {
  date: string;
  model: string;
  requests: number;
  total_tokens: number;
  total_cost_usd: number;
};
export type ConfigBackupStatsSnapshot = {
  imported_total?: ConfigBackupImportedStatsTotal | null;
  imported_daily: ConfigBackupImportedStatsDaily[];
  request_daily: ConfigBackupRequestLogDailyStat[];
  model_daily: ConfigBackupOverviewModelDailyStat[];
};
export type ConfigBackupGatewayApiKey = {
  id: string;
  remark: string;
  api_key: string;
  enabled: boolean;
  allowed_models: string[];
  max_cost_usd: number;
  spent_cost_usd: number;
  expires_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};
export type ConfigBackupRequestLog = {
  protocol: ProtocolKind;
  user_agent: string;
  requested_group_name?: string | null;
  resolved_group_name?: string | null;
  upstream_model_name?: string | null;
  channel_id?: string | null;
  channel_name?: string | null;
  gateway_key_id?: string | null;
  status_code?: number | null;
  success: boolean;
  lifecycle_status: RequestLogLifecycleStatus;
  is_stream: boolean;
  first_token_latency_ms: number;
  latency_ms: number;
  input_tokens: number;
  cache_read_input_tokens: number;
  cache_write_input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_cost_usd: number;
  output_cost_usd: number;
  total_cost_usd: number;
  error_message?: string | null;
  created_at: string;
  stats_archived: boolean;
  request_content?: string | null;
  response_content?: string | null;
  attempts: RequestLogAttempt[];
};
export type ConfigBackupDump = {
  version: number;
  exported_at: string;
  lens_version: string;
  include_request_logs: boolean;
  include_gateway_api_keys: boolean;
  settings: SettingItem[];
  sites: Site[];
  groups: ModelGroup[];
  model_prices: ModelPriceItem[];
  cronjobs: Array<{
    id: string;
    enabled: boolean;
    schedule_type: CronjobScheduleType;
    interval_hours: number;
    run_at_time?: string | null;
    weekdays: number[];
  }>;
  stats: ConfigBackupStatsSnapshot;
  gateway_api_keys: ConfigBackupGatewayApiKey[];
  request_logs: ConfigBackupRequestLog[];
};
export type ConfigImportResult = { rows_affected: Record<string, number> };

/** Downloads a configuration backup with the requested optional sections. */
export async function downloadConfigBackup(options?: {
  shouldIncludeLogs?: boolean;
  shouldIncludeGatewayApiKeys?: boolean;
}) {
  const params = new URLSearchParams();
  params.set("include_logs", String(Boolean(options?.shouldIncludeLogs)));
  params.set(
    "include_gateway_api_keys",
    String(Boolean(options?.shouldIncludeGatewayApiKeys)),
  );
  const response = await apiFetch(
    "/admin/backups/export?" + params.toString(),
    { method: "GET" },
  );
  const blob = await response.blob();
  const match = response.headers
    .get("content-disposition")
    ?.match(/filename="([^"]+)"/i);
  const filename =
    match?.[1] ??
    `lens-backup-${new Date().toISOString().replace(/\D/g, "").slice(0, 14)}.json`;
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
  return { filename };
}

/** Imports a configuration backup file through the admin API. */
export async function importConfigBackup(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<ConfigImportResult>("/admin/backups/import", {
    method: "POST",
    body: formData,
  });
}
