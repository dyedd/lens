import type { PluginItem, PluginState } from "@/lib/api/plugins";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import { taskTitle } from "../cronjobs/taskLabels";

const PLUGIN_DESCRIPTIONS: Record<string, [string, string]> = {
  request_log_prune: [
    "按日志保留天数清理过期请求日志",
    "Remove expired request logs by the retention period",
  ],
  model_price_sync: [
    "从 LiteLLM 同步模型价格",
    "Sync model prices from LiteLLM",
  ],
  request_log_stats_persist: [
    "归档请求日志统计数据",
    "Archive request log statistics",
  ],
  version_check: [
    "检测 GitHub releases 是否有新版本",
    "Check GitHub releases for a newer version",
  ],
  channel_model_sync: [
    "为启用的渠道拉取上游模型，按凭证规则保存匹配项",
    "Pull upstream models for enabled channels and keep the credential matches",
  ],
  credential_rate_sync: [
    "同步 Sub2API 有效倍率与 NewAPI 分组参考倍率",
    "Sync Sub2API effective rates and NewAPI group reference rates",
  ],
};

const STATE_LABELS: Record<PluginState, [string, string]> = {
  active: ["已启用", "Enabled"],
  disabled: ["已停用", "Disabled"],
  failed: ["异常", "Failed"],
};

export function pluginTitle(locale: Locale, plugin: PluginItem) {
  return taskTitle(locale, plugin.id, plugin.name);
}

export function pluginDescription(locale: Locale, plugin: PluginItem) {
  const text = PLUGIN_DESCRIPTIONS[plugin.id];
  return text ? titleForLocale(locale, text[0], text[1]) : plugin.description;
}

export function pluginStateLabel(locale: Locale, state: PluginState) {
  const label = STATE_LABELS[state];
  return titleForLocale(locale, label[0], label[1]);
}

export function pluginCronjobTitles(locale: Locale, plugin: PluginItem) {
  return plugin.cronjobs.map((task) => taskTitle(locale, task.id, task.name));
}
