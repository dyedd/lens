import { GatewaySettings } from "@/components/settings/GatewaySettings";
import { TabsContent } from "@/components/ui/Tabs";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { SettingsSectionCard } from "./SettingsSectionCard";
import { type useSettingsDraft } from "./useSettingsDraft";

type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

/** Render the gateway settings tab content. */
export function GatewaySettingsSection({
  description,
  locale,
  settings,
}: {
  description: string;
  locale: Locale;
  settings: SettingsDraftController;
}) {
  const { draft } = settings;

  return (
    <TabsContent value="gateway" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(locale, "网关", "Gateway")}
        description={description}
      >
        <GatewaySettings
          proxyUrl={draft.proxyUrl}
          corsAllowOrigins={draft.corsAllowOrigins}
          authAccessTokenMinutes={draft.authAccessTokenMinutes}
          firstTokenTimeoutSeconds={draft.firstTokenTimeoutSeconds}
          streamIdleTimeoutSeconds={draft.streamIdleTimeoutSeconds}
          maxRequestBodyBytes={draft.maxRequestBodyBytes}
          authAccessTokenMinutesError={
            settings.numericSettingErrors.authAccessTokenMinutes
          }
          firstTokenTimeoutSecondsError={
            settings.numericSettingErrors.firstTokenTimeoutSeconds
          }
          streamIdleTimeoutSecondsError={
            settings.numericSettingErrors.streamIdleTimeoutSeconds
          }
          maxRequestBodyBytesError={
            settings.numericSettingErrors.maxRequestBodyBytes
          }
          isRelayLogBodyEnabled={draft.isRelayLogBodyEnabled}
          isModelListCompatModeEnabled={draft.isModelListCompatModeEnabled}
          upstreamHeadersConfig={draft.upstreamHeadersConfig}
          onProxyUrlChange={(value) =>
            settings.setDraftValue("proxyUrl", value)
          }
          onCorsAllowOriginsChange={(value) =>
            settings.setDraftValue("corsAllowOrigins", value)
          }
          onAuthAccessTokenMinutesChange={(value) =>
            settings.setDraftValue("authAccessTokenMinutes", value)
          }
          onFirstTokenTimeoutSecondsChange={(value) =>
            settings.setDraftValue("firstTokenTimeoutSeconds", value)
          }
          onStreamIdleTimeoutSecondsChange={(value) =>
            settings.setDraftValue("streamIdleTimeoutSeconds", value)
          }
          onMaxRequestBodyBytesChange={(value) =>
            settings.setDraftValue("maxRequestBodyBytes", value)
          }
          onRelayLogBodyEnabledChange={(isEnabled) =>
            settings.setDraftValue("isRelayLogBodyEnabled", isEnabled)
          }
          onModelListCompatModeEnabledChange={(isEnabled) =>
            settings.setDraftValue("isModelListCompatModeEnabled", isEnabled)
          }
          onAddGlobalHeader={settings.addGlobalHeader}
          onUpdateGlobalHeader={settings.updateGlobalHeader}
          onRemoveGlobalHeader={settings.removeGlobalHeader}
          onAddRule={settings.addUpstreamHeaderRule}
          onUpdateRule={settings.updateUpstreamHeaderRule}
          onRemoveRule={settings.removeUpstreamHeaderRule}
          onMoveRule={settings.moveUpstreamHeaderRule}
          onAddRuleHeader={settings.addRuleHeader}
          onUpdateRuleHeader={settings.updateRuleHeader}
          onRemoveRuleHeader={settings.removeRuleHeader}
          upstreamParamOverrideConfig={draft.upstreamParamOverrideConfig}
          onGlobalParamOverrideChange={settings.updateGlobalParamOverride}
          onAddParamOverrideRule={settings.addParamOverrideRule}
          onUpdateParamOverrideRule={settings.updateParamOverrideRule}
          onRemoveParamOverrideRule={settings.removeParamOverrideRule}
          onMoveParamOverrideRule={settings.moveParamOverrideRule}
        />
      </SettingsSectionCard>
    </TabsContent>
  );
}
