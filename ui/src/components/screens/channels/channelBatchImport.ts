import type { SiteBatchImportPayload, SiteBatchImportResult } from "@/lib/api";
import type { Locale } from "@/lib/I18nContext";
import type { BatchModelTestStatus, ImportResultRow } from "./channelTypes";

export const BATCH_IMPORT_TEMPLATE: SiteBatchImportPayload = {
  sites: [
    {
      name: "OpenAI",
      base_urls: [
        {
          ref: "main",
          url: "https://api.openai.com/v1",
          name: "",
          enabled: true,
        },
      ],
      credentials: [
        {
          ref: "key1",
          name: "Key 1",
          api_key: "sk-...",
          enabled: true,
        },
      ],
      protocols: [
        {
          protocol: "openai_chat",
          enabled: true,
          base_url_ref: "main",
          credential_ref: "key1",
          headers: {},
          proxy_mode: "inherit",
          channel_proxy: "",
          param_override: "",
          match_regex: "",
          models: [
            {
              model_name: "gpt-4.1",
              credential_ref: "key1",
              enabled: true,
            },
          ],
        },
      ],
    },
  ],
};

/** Serializes the example channel import payload as formatted JSON. */
export function batchImportTemplateText(): string {
  return JSON.stringify(BATCH_IMPORT_TEMPLATE, null, 2);
}

/** Reports whether a value is a non-array object record. */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/** Parses and validates the top-level shape of a channel import payload. */
export function parseBatchImportPayload(
  text: string,
  locale: Locale,
): SiteBatchImportPayload {
  const content = text.trim();
  if (!content) {
    throw new Error(locale === "zh-CN" ? "JSON 内容为空" : "JSON is empty");
  }

  let value: unknown;
  try {
    value = JSON.parse(content);
  } catch {
    throw new Error(
      locale === "zh-CN" ? "JSON 格式无效" : "Invalid JSON format",
    );
  }

  if (!isRecord(value) || !Array.isArray(value.sites)) {
    throw new Error(
      locale === "zh-CN"
        ? "JSON 必须包含 sites 数组"
        : "JSON must include a sites array",
    );
  }

  return value as SiteBatchImportPayload;
}

export function importReasonLabel(reason: string, locale: Locale): string {
  if (reason === "duplicate_name") {
    return locale === "zh-CN" ? "同名渠道已存在" : "Channel already exists";
  }
  if (reason === "duplicate_in_file") {
    return locale === "zh-CN" ? "文件内重名" : "Duplicate in file";
  }
  return reason;
}

/** Formats a channel import status for the requested locale. */
export function importStatusLabel(
  status: ImportResultRow["status"],
  locale: Locale,
): string {
  if (status === "created") return locale === "zh-CN" ? "已创建" : "Created";
  if (status === "skipped") return locale === "zh-CN" ? "已跳过" : "Skipped";
  return locale === "zh-CN" ? "错误" : "Error";
}

/** Maps a channel import status to its badge variant. */
export function importStatusVariant(
  status: ImportResultRow["status"],
): "default" | "secondary" | "destructive" {
  if (status === "created") return "default";
  if (status === "skipped") return "secondary";
  return "destructive";
}

/** Formats a batch model-test status for the requested locale. */
export function batchTestStatusLabel(
  status: BatchModelTestStatus,
  locale: Locale,
) {
  if (status === "pending") return locale === "zh-CN" ? "等待中" : "Pending";
  if (status === "running") return locale === "zh-CN" ? "测试中" : "Running";
  if (status === "success") return locale === "zh-CN" ? "成功" : "Success";
  return locale === "zh-CN" ? "失败" : "Failed";
}

/** Maps a batch model-test status to its badge variant. */
export function batchTestStatusVariant(
  status: BatchModelTestStatus,
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "success") return "default";
  if (status === "failed") return "destructive";
  if (status === "running") return "secondary";
  return "outline";
}

/** Flattens a channel import result into display rows. */
export function importResultRows(
  result: SiteBatchImportResult,
  locale: Locale,
): ImportResultRow[] {
  return [
    ...result.created.map((site, index) => ({
      key: `created-${site.id}`,
      index,
      name: site.name,
      status: "created" as const,
      reason: "",
    })),
    ...result.skipped.map((item) => ({
      key: `skipped-${item.index}-${item.name}`,
      index: item.index,
      name: item.name,
      status: "skipped" as const,
      reason: importReasonLabel(item.reason, locale),
    })),
    ...result.errors.map((item) => ({
      key: `error-${item.index}-${item.field}-${item.message}`,
      index: item.index,
      name: item.field,
      status: "error" as const,
      reason: item.message,
    })),
  ];
}
