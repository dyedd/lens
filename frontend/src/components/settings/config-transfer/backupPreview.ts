import type { Locale } from "@/lib/I18nContext";

export type ConfigBackupPreview = {
  exported_at: string;
  lens_version: string;
  include_request_logs: boolean;
  include_gateway_api_keys: boolean;
  counts: Record<
    | "settings"
    | "sites"
    | "groups"
    | "model_prices"
    | "cronjobs"
    | "stats"
    | "gateway_api_keys"
    | "request_logs",
    number
  >;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function arrayLength(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

export function parseBackupPreview(rawValue: string): ConfigBackupPreview {
  const payload: unknown = JSON.parse(rawValue);
  if (!isRecord(payload)) throw new Error("Invalid backup file");
  const stats = isRecord(payload.stats) ? payload.stats : {};
  return {
    exported_at:
      typeof payload.exported_at === "string" ? payload.exported_at : "",
    lens_version:
      typeof payload.lens_version === "string" ? payload.lens_version : "",
    include_request_logs: payload.include_request_logs === true,
    include_gateway_api_keys: payload.include_gateway_api_keys === true,
    counts: {
      settings: arrayLength(payload.settings),
      sites: arrayLength(payload.sites),
      groups: arrayLength(payload.groups),
      model_prices: arrayLength(payload.model_prices),
      cronjobs: arrayLength(payload.cronjobs),
      gateway_api_keys: arrayLength(payload.gateway_api_keys),
      request_logs: arrayLength(payload.request_logs),
      stats:
        Number(isRecord(stats.imported_total)) +
        arrayLength(stats.imported_daily) +
        arrayLength(stats.request_daily) +
        arrayLength(stats.model_daily),
    },
  };
}

export function formatExportedAt(
  value: string,
  locale: Locale,
  timeZone?: string,
) {
  if (!value) {
    return "n/a";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(locale === "zh-CN" ? "zh-CN" : "en-US", {
    ...(timeZone ? { timeZone } : {}),
  });
}

export function resultLabelForLocale(locale: Locale, key: string) {
  const labels: Record<string, [string, string]> = {
    gateway_api_keys: ["网关密钥", "Gateway keys"],
    groups: ["模型组", "Model groups"],
    imported_stats_daily: ["导入统计(日)", "Imported stats (daily)"],
    imported_stats_total: ["导入统计(总计)", "Imported stats (total)"],
    model_group_items: ["模型组成员", "Model group items"],
    model_groups: ["模型组", "Model groups"],
    model_prices: ["模型价格", "Model prices"],
    overview_model_daily_stats: ["模型统计(日)", "Model stats (daily)"],
    request_log_daily_stats: ["请求统计(日)", "Request stats (daily)"],
    request_logs: ["请求日志", "Request logs"],
    cronjobs: ["计划任务", "Scheduled tasks"],
    settings: ["系统设置", "System settings"],
    site_base_urls: ["渠道地址", "Channel URLs"],
    site_credentials: ["渠道 API Key", "Channel API keys"],
    site_models: ["发现模型", "Discovered models"],
    site_protocol_configs: ["渠道协议配置", "Channel protocol configs"],
    sites: ["渠道", "Channels"],
  };
  const label = labels[key];
  if (!label) {
    return key;
  }
  return locale === "zh-CN" ? label[0] : label[1];
}
