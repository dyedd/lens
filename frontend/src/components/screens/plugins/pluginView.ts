import type {
  PluginExtensionStats,
  PluginItem,
  PluginState,
} from "@/lib/api/plugins";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

const EXTENSION_LABELS: Record<string, [string, string]> = {
  request_rewrite: ["请求改写", "Request rewrite"],
  upstream_request: ["出站改写", "Outbound rewrite"],
  upstream_credential: ["渠道鉴权", "Channel credential"],
  upstream_response: ["响应改写", "Response rewrite"],
  response_event: ["流式事件", "Stream events"],
  request_observer: ["请求观察", "Request observer"],
  model_catalog: ["模型目录", "Model catalog"],
  route_strategy: ["路由策略", "Routing strategy"],
};

const STATE_LABELS: Record<PluginState, [string, string]> = {
  active: ["已启用", "Enabled"],
  pending: ["等待依赖", "Waiting"],
  disabled: ["已停用", "Disabled"],
  failed: ["异常", "Failed"],
};

export function pluginStateLabel(locale: Locale, state: PluginState) {
  const label = STATE_LABELS[state];
  return titleForLocale(locale, label[0], label[1]);
}

export function pluginExtensionLabel(locale: Locale, extension: string) {
  const label = EXTENSION_LABELS[extension];
  return label ? titleForLocale(locale, label[0], label[1]) : extension;
}

/** 调用次数与平均耗时；没有调用时返回空串。 */
export function formatExtensionUsage(
  locale: Locale,
  stats: PluginExtensionStats,
) {
  if (!stats.calls) return "";
  const calls = stats.calls.toLocaleString(locale);
  const avgMs = stats.avg_ms.toLocaleString(locale, {
    maximumFractionDigits: 1,
  });
  return titleForLocale(
    locale,
    `调用 ${calls} · 平均 ${avgMs} ms`,
    `${calls} ${stats.calls === 1 ? "call" : "calls"} · avg ${avgMs} ms`,
  );
}

/** 失败与丢弃次数，只列出非零项。 */
export function formatExtensionFailures(
  locale: Locale,
  stats: PluginExtensionStats,
) {
  const parts: string[] = [];
  if (stats.failures) {
    const failures = stats.failures.toLocaleString(locale);
    parts.push(
      titleForLocale(locale, `失败 ${failures}`, `${failures} failed`),
    );
  }
  if (stats.dropped) {
    const dropped = stats.dropped.toLocaleString(locale);
    parts.push(titleForLocale(locale, `丢弃 ${dropped}`, `${dropped} dropped`));
  }
  return parts.join(" · ");
}

/** 作者与来源合成一行副标题，缺省项直接省略。 */
export function pluginOriginLabel(locale: Locale, plugin: PluginItem) {
  const source =
    plugin.source === "external"
      ? titleForLocale(locale, "外部", "External")
      : titleForLocale(locale, "内置", "Built-in");
  return plugin.author ? `${plugin.author} · ${source}` : source;
}
