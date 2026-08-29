import type { Locale } from "@/lib/I18nContext";
import type { UpstreamParamOverrideDraft } from "@/lib/settingsTypes";

export type HeaderItem = { key: string; value: string };

export type UpstreamHeadersDraft = {
  global: HeaderItem[];
};

export type GatewayGeneralSettingsProps = {
  locale: Locale;
  proxyUrl: string;
  corsAllowOrigins: string;
  authAccessTokenMinutes: string;
  firstTokenTimeoutSeconds: string;
  streamIdleTimeoutSeconds: string;
  maxRequestBodyBytes: string;
  authAccessTokenMinutesError?: string;
  firstTokenTimeoutSecondsError?: string;
  streamIdleTimeoutSecondsError?: string;
  maxRequestBodyBytesError?: string;
  isRelayLogBodyEnabled: boolean;
  isModelListCompatModeEnabled: boolean;
  onProxyUrlChange: (value: string) => void;
  onCorsAllowOriginsChange: (value: string) => void;
  onAuthAccessTokenMinutesChange: (value: string) => void;
  onFirstTokenTimeoutSecondsChange: (value: string) => void;
  onStreamIdleTimeoutSecondsChange: (value: string) => void;
  onMaxRequestBodyBytesChange: (value: string) => void;
  onRelayLogBodyEnabledChange: (checked: boolean) => void;
  onModelListCompatModeEnabledChange: (checked: boolean) => void;
};

export type UpstreamHeaderSettingsProps = {
  locale: Locale;
  config: UpstreamHeadersDraft;
  onAddGlobalHeader: () => void;
  onUpdateGlobalHeader: (index: number, patch: Partial<HeaderItem>) => void;
  onRemoveGlobalHeader: (index: number) => void;
};

export type ParamOverrideSettingsProps = {
  locale: Locale;
  config: UpstreamParamOverrideDraft;
  onGlobalChange: (value: string) => void;
};
