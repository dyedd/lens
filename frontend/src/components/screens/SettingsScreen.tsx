import { RotateCcw, RotateCw } from "lucide-react";
import { useMemo, useState } from "react";
import { CircuitBreakerSettingsSection } from "@/components/settings/CircuitBreakerSettingsSection";
import { GatewaySettingsSection } from "@/components/settings/GatewaySettingsSection";
import { PrivacySettingsSection } from "@/components/settings/PrivacySettingsSection";
import { GeneralSettingsSection } from "@/components/settings/ProfileSettingsSections";
import {
  createSettingsTabs,
  SettingsNavigation,
} from "@/components/settings/SettingsNavigation";
import { useAccountSettings } from "@/components/settings/useAccountSettings";
import { useSettingsDraft } from "@/components/settings/useSettingsDraft";
import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { type Locale, titleForLocale, useI18n } from "@/lib/I18nContext";
import { ApiKeysScreen } from "./ApiKeysScreen";
import { BackupsScreen } from "./BackupsScreen";
import { CronjobsScreen } from "./CronjobsScreen";

type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

function SettingsHeaderActions({
  locale,
  settings,
  showRefresh = true,
}: {
  locale: Locale;
  settings: SettingsDraftController;
  showRefresh?: boolean;
}) {
  const refreshLabel = titleForLocale(locale, "刷新", "Refresh");
  const retryLabel = titleForLocale(locale, "重试保存", "Retry saving");

  return (
    <DashboardHeaderActions>
      <div className="flex items-center justify-end gap-2">
        {settings.hasSaveError && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                type="button"
                aria-label={retryLabel}
                disabled={settings.isSaving}
                onClick={settings.retrySettings}
              >
                <RotateCw data-icon="inline-start" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {retryLabel}
            </TooltipContent>
          </Tooltip>
        )}
        {showRefresh && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                type="button"
                aria-label={refreshLabel}
                onClick={() => void settings.refresh()}
              >
                <RotateCcw data-icon="inline-start" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {refreshLabel}
            </TooltipContent>
          </Tooltip>
        )}
      </div>
    </DashboardHeaderActions>
  );
}

/** Render application, gateway, appearance, and account settings. */
export function SettingsScreen() {
  const { locale } = useI18n();
  const settings = useSettingsDraft(locale);
  const account = useAccountSettings(locale);
  const settingsTabs = useMemo(() => createSettingsTabs(locale), [locale]);
  const [activeTab, setActiveTab] = useState("general");

  return (
    <>
      {(activeTab !== "cronjobs" || settings.hasSaveError) && (
        <SettingsHeaderActions
          locale={locale}
          settings={settings}
          showRefresh={activeTab !== "cronjobs"}
        />
      )}
      <section className="mx-auto min-w-0 max-w-[1320px] space-y-5">
        <PageHeader title={titleForLocale(locale, "设置", "Settings")} />
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          orientation="horizontal"
          className="flex min-w-0 flex-col gap-6"
        >
          <SettingsNavigation tabs={settingsTabs} />
          <div className="min-w-0">
            <GeneralSettingsSection
              locale={locale}
              settings={settings}
              account={account}
            />
            <GatewaySettingsSection locale={locale} settings={settings} />
            <PrivacySettingsSection locale={locale} settings={settings} />
            <CircuitBreakerSettingsSection
              locale={locale}
              settings={settings}
            />
            <TabsContent value="api-keys" className="mt-0">
              <ApiKeysScreen />
            </TabsContent>
            <TabsContent value="cronjobs" className="mt-0">
              <CronjobsScreen />
            </TabsContent>
            <TabsContent value="backups" className="mt-0">
              <BackupsScreen />
            </TabsContent>
          </div>
        </Tabs>
      </section>
    </>
  );
}
