import { FieldGroup } from "@/components/ui/Field";
import { useI18n } from "@/lib/I18nContext";
import type { UpstreamParamOverrideDraft } from "@/lib/upstreamRules";
import { GatewayGeneralSettings } from "./gateway-settings/GatewayGeneralSettings";
import type {
  HeaderItem,
  UpstreamHeadersDraft,
} from "./gateway-settings/gatewaySettingsTypes";
import { ParamOverrideSettings } from "./gateway-settings/ParamOverrideSettings";
import { UpstreamHeaderSettings } from "./gateway-settings/UpstreamHeaderSettings";

interface GatewaySettingsProps {
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
  upstreamHeadersConfig: UpstreamHeadersDraft;
  upstreamParamOverrideConfig: UpstreamParamOverrideDraft;
  onProxyUrlChange: (value: string) => void;
  onCorsAllowOriginsChange: (value: string) => void;
  onAuthAccessTokenMinutesChange: (value: string) => void;
  onFirstTokenTimeoutSecondsChange: (value: string) => void;
  onStreamIdleTimeoutSecondsChange: (value: string) => void;
  onMaxRequestBodyBytesChange: (value: string) => void;
  onRelayLogBodyEnabledChange: (checked: boolean) => void;
  onModelListCompatModeEnabledChange: (checked: boolean) => void;
  onAddGlobalHeader: () => void;
  onUpdateGlobalHeader: (index: number, patch: Partial<HeaderItem>) => void;
  onRemoveGlobalHeader: (index: number) => void;
  onGlobalParamOverrideChange: (
    rules: UpstreamParamOverrideDraft["rules"],
  ) => void;
}

/** Renders gateway proxy, CORS, logging, header, and override settings. */
export function GatewaySettings({
  proxyUrl,
  corsAllowOrigins,
  authAccessTokenMinutes,
  firstTokenTimeoutSeconds,
  streamIdleTimeoutSeconds,
  maxRequestBodyBytes,
  authAccessTokenMinutesError,
  firstTokenTimeoutSecondsError,
  streamIdleTimeoutSecondsError,
  maxRequestBodyBytesError,
  isRelayLogBodyEnabled,
  isModelListCompatModeEnabled,
  upstreamHeadersConfig,
  upstreamParamOverrideConfig,
  onProxyUrlChange,
  onCorsAllowOriginsChange,
  onAuthAccessTokenMinutesChange,
  onFirstTokenTimeoutSecondsChange,
  onStreamIdleTimeoutSecondsChange,
  onMaxRequestBodyBytesChange,
  onRelayLogBodyEnabledChange,
  onModelListCompatModeEnabledChange,
  onAddGlobalHeader,
  onUpdateGlobalHeader,
  onRemoveGlobalHeader,
  onGlobalParamOverrideChange,
}: GatewaySettingsProps) {
  const { locale } = useI18n();

  return (
    <FieldGroup>
      <GatewayGeneralSettings
        locale={locale}
        proxyUrl={proxyUrl}
        corsAllowOrigins={corsAllowOrigins}
        authAccessTokenMinutes={authAccessTokenMinutes}
        firstTokenTimeoutSeconds={firstTokenTimeoutSeconds}
        streamIdleTimeoutSeconds={streamIdleTimeoutSeconds}
        maxRequestBodyBytes={maxRequestBodyBytes}
        authAccessTokenMinutesError={authAccessTokenMinutesError}
        firstTokenTimeoutSecondsError={firstTokenTimeoutSecondsError}
        streamIdleTimeoutSecondsError={streamIdleTimeoutSecondsError}
        maxRequestBodyBytesError={maxRequestBodyBytesError}
        isRelayLogBodyEnabled={isRelayLogBodyEnabled}
        isModelListCompatModeEnabled={isModelListCompatModeEnabled}
        onProxyUrlChange={onProxyUrlChange}
        onCorsAllowOriginsChange={onCorsAllowOriginsChange}
        onAuthAccessTokenMinutesChange={onAuthAccessTokenMinutesChange}
        onFirstTokenTimeoutSecondsChange={onFirstTokenTimeoutSecondsChange}
        onStreamIdleTimeoutSecondsChange={onStreamIdleTimeoutSecondsChange}
        onMaxRequestBodyBytesChange={onMaxRequestBodyBytesChange}
        onRelayLogBodyEnabledChange={onRelayLogBodyEnabledChange}
        onModelListCompatModeEnabledChange={onModelListCompatModeEnabledChange}
      />
      <UpstreamHeaderSettings
        locale={locale}
        config={upstreamHeadersConfig}
        onAddGlobalHeader={onAddGlobalHeader}
        onUpdateGlobalHeader={onUpdateGlobalHeader}
        onRemoveGlobalHeader={onRemoveGlobalHeader}
      />
      <ParamOverrideSettings
        locale={locale}
        config={upstreamParamOverrideConfig}
        onGlobalChange={onGlobalParamOverrideChange}
      />
    </FieldGroup>
  );
}
