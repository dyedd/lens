import { titleForLocale } from "@/lib/I18nContext";

import type { UpstreamHeaderSettingsProps } from "./gatewaySettingsTypes";
import { HeaderRows } from "./HeaderRows";

/** Renders global upstream request-header settings. */
export function UpstreamHeaderSettings({
  locale,
  config,
  onAddGlobalHeader,
  onUpdateGlobalHeader,
  onRemoveGlobalHeader,
}: UpstreamHeaderSettingsProps) {
  return (
    <HeaderRows
      title={titleForLocale(locale, "全局请求头", "Global headers")}
      headers={config.rules}
      locale={locale}
      onAdd={onAddGlobalHeader}
      onUpdate={onUpdateGlobalHeader}
      onRemove={onRemoveGlobalHeader}
    />
  );
}
