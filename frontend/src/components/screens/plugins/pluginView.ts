import type { PluginItem, PluginState } from "@/lib/api/plugins";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

const PLUGIN_TITLES: Record<string, [string, string]> = {
  channel_credential_bridge: ["自定义渠道凭据", "Custom channel credential"],
  response_header_stamp: ["响应标记", "Response stamp"],
};

const PLUGIN_DESCRIPTIONS: Record<string, [string, string]> = {
  channel_credential_bridge: [
    "为指定渠道改用插件提供的鉴权头，并改写请求、补齐模型、观察请求",
    "Swap a channel credential for one the plugin issues",
  ],
  response_header_stamp: [
    "给经自定义渠道凭据插件处理的响应补一个标记头",
    "Stamp responses handled by the credential plugin",
  ],
};

const EXTENSION_LABELS: Record<string, [string, string]> = {
  upstream_request: ["请求改写", "Request rewrite"],
  upstream_credential: ["渠道鉴权", "Channel credential"],
  upstream_response: ["响应改写", "Response rewrite"],
  request_observer: ["请求观察", "Request observer"],
  model_catalog: ["模型目录", "Model catalog"],
};

const STATE_LABELS: Record<PluginState, [string, string]> = {
  active: ["已启用", "Enabled"],
  pending: ["等待依赖", "Waiting"],
  disabled: ["已停用", "Disabled"],
  failed: ["异常", "Failed"],
};

export function pluginTitle(locale: Locale, plugin: PluginItem) {
  const label = PLUGIN_TITLES[plugin.id];
  return label ? titleForLocale(locale, label[0], label[1]) : plugin.name;
}

export function pluginDescription(locale: Locale, plugin: PluginItem) {
  const text = PLUGIN_DESCRIPTIONS[plugin.id];
  return text ? titleForLocale(locale, text[0], text[1]) : plugin.description;
}

export function pluginStateLabel(locale: Locale, state: PluginState) {
  const label = STATE_LABELS[state];
  return titleForLocale(locale, label[0], label[1]);
}

export function pluginExtensionLabels(locale: Locale, plugin: PluginItem) {
  return plugin.extensions.map((extension) => {
    const label = EXTENSION_LABELS[extension];
    return label ? titleForLocale(locale, label[0], label[1]) : extension;
  });
}

/** 作者与来源合成一行副标题，缺省项直接省略。 */
export function pluginOriginLabel(locale: Locale, plugin: PluginItem) {
  const source =
    plugin.source === "external"
      ? titleForLocale(locale, "外部", "External")
      : titleForLocale(locale, "内置", "Built-in");
  return plugin.author ? `${plugin.author} · ${source}` : source;
}
