import type { CronjobItem } from "@/lib/api/cronjobs";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import { formatScheduleSummary } from "./CronjobEditors";
import { taskDraft } from "./cronjobDrafts";

const TASK_TITLES: Record<string, [string, string]> = {
  request_log_prune: ["请求日志清理", "Request log cleanup"],
  model_price_sync: ["模型价格同步", "Model price sync"],
  request_log_stats_persist: [
    "请求日志统计归档",
    "Archive request log statistics",
  ],
  version_check: ["版本检测", "Version check"],
  channel_model_sync: ["渠道模型同步", "Channel model sync"],
  credential_rate_sync: ["凭据倍率同步", "Credential rate sync"],
};

export function cronjobTitle(locale: Locale, task: CronjobItem) {
  const label = TASK_TITLES[task.id];
  return label ? titleForLocale(locale, label[0], label[1]) : task.name;
}

export function cronjobScheduleLabel(locale: Locale, task: CronjobItem) {
  return formatScheduleSummary(taskDraft(task), locale);
}
