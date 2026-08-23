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
    <div className="flex flex-col gap-5 rounded-lg border bg-muted/20 p-4">
      <HeaderRows
        title={titleForLocale(locale, "全局请求头", "Global headers")}
        headers={config.global}
        locale={locale}
        onAdd={onAddGlobalHeader}
        onUpdate={onUpdateGlobalHeader}
        onRemove={onRemoveGlobalHeader}
      />
    </div>
  );
}
