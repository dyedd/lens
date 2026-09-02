import { ParamRuleRows } from "@/components/ruleEditors/ParamRuleRows";
import { titleForLocale } from "@/lib/I18nContext";
import type { ParamOverrideSettingsProps } from "./gatewaySettingsTypes";

/** Renders the global upstream parameter rules. */
export function ParamOverrideSettings({
  locale,
  config,
  onGlobalChange,
}: ParamOverrideSettingsProps) {
  return (
    <ParamRuleRows
      title={titleForLocale(locale, "全局参数规则", "Global parameter rules")}
      locale={locale}
      rules={config.rules}
      onChange={onGlobalChange}
    />
  );
}
