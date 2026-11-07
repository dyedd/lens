import { TabsContent } from "@/components/ui/Tabs";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import { GatewayGeneralSettings } from "./gateway-settings/GatewayGeneralSettings";
import { ParamOverrideSettings } from "./gateway-settings/ParamOverrideSettings";
import { UpstreamHeaderSettings } from "./gateway-settings/UpstreamHeaderSettings";
import { SettingsSectionCard } from "./SettingsSectionCard";
import { SettingsSectionSeparator } from "./settingsLayout";
import type { useSettingsDraft } from "./useSettingsDraft";

type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

/** Render the gateway settings tab content. */
export function GatewaySettingsSection({
  locale,
  settings,
}: {
  locale: Locale;
  settings: SettingsDraftController;
}) {
  const { draft } = settings;

  return (
    <TabsContent value="gateway" className="mt-0">
      <SettingsSectionCard title={titleForLocale(locale, "网关", "Gateway")}>
        <div className="space-y-6">
          <GatewayGeneralSettings
            locale={locale}
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
          />
          <SettingsSectionSeparator />
          <UpstreamHeaderSettings
            locale={locale}
            config={draft.upstreamHeadersConfig}
            onAddGlobalHeader={settings.addGlobalHeader}
            onUpdateGlobalHeader={settings.updateGlobalHeader}
            onRemoveGlobalHeader={settings.removeGlobalHeader}
          />
          <SettingsSectionSeparator />
          <ParamOverrideSettings
            locale={locale}
            config={draft.upstreamParamOverrideConfig}
            onGlobalChange={(rules) =>
              settings.setDraftValue("upstreamParamOverrideConfig", { rules })
            }
          />
        </div>
      </SettingsSectionCard>
    </TabsContent>
  );
}
