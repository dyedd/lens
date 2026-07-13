import type { Locale } from "@/lib/I18nContext";
import type {
  UpstreamParamOverrideDraft,
  UpstreamParamOverrideRuleDraft,
} from "@/lib/settingsTypes";

export type HeaderItem = { key: string; value: string };

export type UpstreamHeaderMatchType = "exact" | "regex";

export type UpstreamHeaderRuleDraft = {
  id: string;
  enabled: boolean;
  name: string;
  matchType: UpstreamHeaderMatchType;
  models: string;
  pattern: string;
  headers: HeaderItem[];
};

export type UpstreamHeadersDraft = {
  global: HeaderItem[];
  rules: UpstreamHeaderRuleDraft[];
};

export type GatewayGeneralSettingsProps = {
  locale: Locale;
  proxyUrl: string;
  corsAllowOrigins: string;
  isRelayLogBodyEnabled: boolean;
  isModelListCompatModeEnabled: boolean;
  onProxyUrlChange: (value: string) => void;
  onCorsAllowOriginsChange: (value: string) => void;
  onRelayLogBodyEnabledChange: (checked: boolean) => void;
  onModelListCompatModeEnabledChange: (checked: boolean) => void;
};

export type UpstreamHeaderSettingsProps = {
  locale: Locale;
  config: UpstreamHeadersDraft;
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
};

export type ParamOverrideSettingsProps = {
  locale: Locale;
  config: UpstreamParamOverrideDraft;
  onGlobalChange: (value: string) => void;
  onAddRule: () => void;
  onUpdateRule: (
    index: number,
    patch: Partial<UpstreamParamOverrideRuleDraft>,
  ) => void;
  onRemoveRule: (index: number) => void;
  onMoveRule: (index: number, direction: -1 | 1) => void;
};
