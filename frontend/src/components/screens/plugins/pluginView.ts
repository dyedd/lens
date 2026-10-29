import type { PluginItem, PluginState } from "@/lib/api/plugins";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

const PLUGIN_TITLES: Record<string, [string, string]> = {
  channel_credential_bridge: ["自定义渠道凭据", "Custom channel credential"],
};

const PLUGIN_DESCRIPTIONS: Record<string, [string, string]> = {
  channel_credential_bridge: [
    "为指定渠道改用插件提供的鉴权头，并改写它的出站请求",
    "Swap a channel's upstream credential for one the plugin supplies",
  ],
};

const EXTENSION_LABELS: Record<string, [string, string]> = {
  upstream_credential: ["渠道鉴权", "Channel credential"],
  upstream_headers: ["请求改写", "Request rewrite"],
};

const STATE_LABELS: Record<PluginState, [string, string]> = {
  active: ["已启用", "Enabled"],
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
