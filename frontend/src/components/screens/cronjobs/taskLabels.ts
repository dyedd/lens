import { type Locale, titleForLocale } from "@/lib/I18nContext";

/** 计划任务的本地化标题，按 id 对齐后端清单。 */
export const TASK_TITLES: Record<string, [string, string]> = {
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

/** 返回任务或插件的本地化标题，未登记的 id 回落到后端给出的名称。 */
export function taskTitle(locale: Locale, taskId: string, fallback: string) {
  const label = TASK_TITLES[taskId];
  return label ? titleForLocale(locale, label[0], label[1]) : fallback;
}
