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
      "请求日志统计归档",
      "Archive request log statistics",
    ],
    model_price_sync: ["模型价格同步", "Model price sync"],
    channel_model_sync: ["渠道模型同步", "Channel model sync"],
    credential_rate_sync: ["凭据倍率同步", "Credential rate sync"],
    version_check: ["版本检测", "Version check"],
  };
  const label = labels[task.id];
  return label ? titleForLocale(locale, label[0], label[1]) : task.name;
}

export function cronjobScheduleLabel(locale: Locale, task: CronjobItem) {
  return formatScheduleSummary(taskDraft(task), locale);
}
