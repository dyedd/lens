"use client";

import { FieldGroup } from "@/components/ui/Field";
import { useI18n } from "@/lib/I18nContext";
import type {
  UpstreamParamOverrideDraft,
  UpstreamParamOverrideRuleDraft,
} from "@/lib/settingsTypes";

import { GatewayGeneralSettings } from "./gateway-settings/GatewayGeneralSettings";
import type {
  HeaderItem,
  UpstreamHeaderRuleDraft,
  UpstreamHeadersDraft,
} from "./gateway-settings/gatewaySettingsTypes";
import { ParamOverrideSettings } from "./gateway-settings/ParamOverrideSettings";
import { UpstreamHeaderSettings } from "./gateway-settings/UpstreamHeaderSettings";

interface GatewaySettingsProps {
  proxyUrl: string;
  corsAllowOrigins: string;
  isRelayLogBodyEnabled: boolean;
  isModelListCompatModeEnabled: boolean;
  upstreamHeadersConfig: UpstreamHeadersDraft;
  upstreamParamOverrideConfig: UpstreamParamOverrideDraft;
  onProxyUrlChange: (value: string) => void;
  onCorsAllowOriginsChange: (value: string) => void;
  onRelayLogBodyEnabledChange: (checked: boolean) => void;
  onModelListCompatModeEnabledChange: (checked: boolean) => void;
  onAddGlobalHeader: () => void;
  onUpdateGlobalHeader: (index: number, patch: Partial<HeaderItem>) => void;
  onRemoveGlobalHeader: (index: number) => void;
  onAddRule: () => void;
  onUpdateRule: (
    index: number,
    patch: Partial<UpstreamHeaderRuleDraft>,
  ) => void;
  onRemoveRule: (index: number) => void;
  onMoveRule: (index: number, direction: -1 | 1) => void;
  onAddRuleHeader: (ruleIndex: number) => void;
  onUpdateRuleHeader: (
    ruleIndex: number,
    headerIndex: number,
    patch: Partial<HeaderItem>,
  ) => void;
  onRemoveRuleHeader: (ruleIndex: number, headerIndex: number) => void;
  onGlobalParamOverrideChange: (value: string) => void;
  onAddParamOverrideRule: () => void;
  onUpdateParamOverrideRule: (
    index: number,
    patch: Partial<UpstreamParamOverrideRuleDraft>,
  ) => void;
  onRemoveParamOverrideRule: (index: number) => void;
  onMoveParamOverrideRule: (index: number, direction: -1 | 1) => void;
}

/** Renders gateway proxy, CORS, logging, header, and override settings. */
export function GatewaySettings({
  proxyUrl,
  corsAllowOrigins,
  isRelayLogBodyEnabled,
  isModelListCompatModeEnabled,
  upstreamHeadersConfig,
  upstreamParamOverrideConfig,
  onProxyUrlChange,
  onCorsAllowOriginsChange,
  onRelayLogBodyEnabledChange,
  onModelListCompatModeEnabledChange,
  onAddGlobalHeader,
  onUpdateGlobalHeader,
  onRemoveGlobalHeader,
  onAddRule,
  onUpdateRule,
  onRemoveRule,
  onMoveRule,
  onAddRuleHeader,
  onUpdateRuleHeader,
  onRemoveRuleHeader,
  onGlobalParamOverrideChange,
  onAddParamOverrideRule,
  onUpdateParamOverrideRule,
  onRemoveParamOverrideRule,
  onMoveParamOverrideRule,
}: GatewaySettingsProps) {
  const { locale } = useI18n();

  return (
    <FieldGroup>
      <GatewayGeneralSettings
        locale={locale}
        proxyUrl={proxyUrl}
        corsAllowOrigins={corsAllowOrigins}
        isRelayLogBodyEnabled={isRelayLogBodyEnabled}
        isModelListCompatModeEnabled={isModelListCompatModeEnabled}
        onProxyUrlChange={onProxyUrlChange}
        onCorsAllowOriginsChange={onCorsAllowOriginsChange}
        onRelayLogBodyEnabledChange={onRelayLogBodyEnabledChange}
        onModelListCompatModeEnabledChange={onModelListCompatModeEnabledChange}
      />
      <UpstreamHeaderSettings
        locale={locale}
        config={upstreamHeadersConfig}
        onAddGlobalHeader={onAddGlobalHeader}
        onUpdateGlobalHeader={onUpdateGlobalHeader}
        onRemoveGlobalHeader={onRemoveGlobalHeader}
        onAddRule={onAddRule}
        onUpdateRule={onUpdateRule}
        onRemoveRule={onRemoveRule}
        onMoveRule={onMoveRule}
        onAddRuleHeader={onAddRuleHeader}
        onUpdateRuleHeader={onUpdateRuleHeader}
        onRemoveRuleHeader={onRemoveRuleHeader}
      />
      <ParamOverrideSettings
        locale={locale}
        config={upstreamParamOverrideConfig}
        onGlobalChange={onGlobalParamOverrideChange}
        onAddRule={onAddParamOverrideRule}
        onUpdateRule={onUpdateParamOverrideRule}
        onRemoveRule={onRemoveParamOverrideRule}
        onMoveRule={onMoveParamOverrideRule}
      />
    </FieldGroup>
  );
}
