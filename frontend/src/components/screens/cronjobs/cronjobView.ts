import type { CronjobItem } from "@/lib/api/cronjobs";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import { formatScheduleSummary } from "./CronjobEditors";
import {
  REQUEST_LOG_PRUNE_TASK_ID,
  REQUEST_LOG_STATS_PERSIST_TASK_ID,
  taskDraft,
} from "./cronjobDrafts";

export function cronjobTitle(locale: Locale, task: CronjobItem) {
  const labels: Record<string, [string, string]> = {
    [REQUEST_LOG_PRUNE_TASK_ID]: ["请求日志清理", "Request log cleanup"],
    [REQUEST_LOG_STATS_PERSIST_TASK_ID]: [
      "请求日志统计落库",
      "Request log stats persist",
    ],
    model_price_sync: ["模型价格同步", "Model price sync"],
    channel_model_sync: ["渠道模型同步", "Channel model sync"],
    credential_rate_sync: ["凭据倍率同步", "Credential rate sync"],
    version_check: ["版本检测", "Version check"],
  };
  const label = labels[task.id];
  return label ? titleForLocale(locale, label[0], label[1]) : task.name;
}

export function cronjobDescription(locale: Locale, task: CronjobItem) {
  const labels: Record<string, [string, string]> = {
    [REQUEST_LOG_PRUNE_TASK_ID]: [
      "按日志保留天数清理过期请求日志",
      "Prune request logs by the retention window",
    ],
    [REQUEST_LOG_STATS_PERSIST_TASK_ID]: [
      "归档请求日志统计数据",
      "Persist request log statistics",
    ],
    model_price_sync: [
      "从 LiteLLM 同步模型价格",
      "Sync model prices from LiteLLM",
    ],
    channel_model_sync: [
      "按渠道自动同步配置更新上游模型",
      "Update upstream models from channel auto-sync settings",
    ],
    credential_rate_sync: [
      "同步 Sub2API 有效倍率与 NewAPI 分组参考倍率",
      "Sync Sub2API effective rates and NewAPI group reference rates",
    ],
    version_check: [
      "检测 GitHub releases 是否有新版本",
      "Check GitHub releases for a newer version",
    ],
  };
  const label = labels[task.id];
  return label ? titleForLocale(locale, label[0], label[1]) : task.description;
}

export function cronjobScheduleLabel(locale: Locale, task: CronjobItem) {
  return formatScheduleSummary(taskDraft(task), locale);
}
