import type { ConfigBackupDump, ConfigBackupStatsSnapshot } from "@/lib/api";
import type { Locale } from "@/lib/I18nContext";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseStatsPreview(value: unknown): ConfigBackupStatsSnapshot {
  if (!isRecord(value)) {
    return {
      imported_total: null,
      imported_daily: [],
      request_daily: [],
      model_daily: [],
    };
  }

  return {
    imported_total: isRecord(value.imported_total)
      ? (value.imported_total as ConfigBackupStatsSnapshot["imported_total"])
      : null,
    imported_daily: Array.isArray(value.imported_daily)
      ? value.imported_daily
      : [],
    request_daily: Array.isArray(value.request_daily)
      ? value.request_daily
      : [],
    model_daily: Array.isArray(value.model_daily) ? value.model_daily : [],
  };
}

export function parseBackupPreview(rawValue: string): ConfigBackupDump {
  const payload = JSON.parse(rawValue);
  if (!isRecord(payload)) {
    throw new Error("Invalid backup file");
  }

  return {
    version: typeof payload.version === "number" ? payload.version : 0,
    exported_at:
      typeof payload.exported_at === "string" ? payload.exported_at : "",
    lens_version:
      typeof payload.lens_version === "string" ? payload.lens_version : "",
    include_request_logs: Boolean(payload.include_request_logs),
    include_gateway_api_keys: Boolean(payload.include_gateway_api_keys),
    settings: Array.isArray(payload.settings) ? payload.settings : [],
    sites: Array.isArray(payload.sites) ? payload.sites : [],
    groups: Array.isArray(payload.groups) ? payload.groups : [],
    model_prices: Array.isArray(payload.model_prices)
      ? payload.model_prices
      : [],
    cronjobs: Array.isArray(payload.cronjobs) ? payload.cronjobs : [],
    stats: parseStatsPreview(payload.stats),
    gateway_api_keys: Array.isArray(payload.gateway_api_keys)
      ? payload.gateway_api_keys
      : [],
    request_logs: Array.isArray(payload.request_logs)
      ? payload.request_logs
      : [],
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
    gateway_api_keys: ["网关 API Key", "Gateway API keys"],
    groups: ["模型组", "Model groups"],
    imported_stats_daily: ["导入统计(日)", "Imported stats (daily)"],
    imported_stats_total: ["导入统计(总计)", "Imported stats (total)"],
    model_group_items: ["模型组成员", "Model group items"],
    model_groups: ["模型组", "Model groups"],
    model_prices: ["模型价格", "Model prices"],
    overview_model_daily_stats: ["模型统计(日)", "Model stats (daily)"],
    request_log_daily_stats: ["请求统计(日)", "Request stats (daily)"],
    request_logs: ["请求日志", "Request logs"],
    cronjobs: ["定时任务", "Cron jobs"],
    settings: ["系统设置", "Settings"],
    site_base_urls: ["渠道地址", "Channel base URLs"],
    site_credentials: ["上游凭据", "Upstream credentials"],
    site_models: ["发现模型", "Discovered models"],
    site_protocol_configs: ["渠道组合", "Channel combinations"],
    sites: ["渠道", "Channels"],
  };
  const label = labels[key];
  if (!label) {
    return key;
  }
  return locale === "zh-CN" ? label[0] : label[1];
}
