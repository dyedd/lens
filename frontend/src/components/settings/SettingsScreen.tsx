import { RotateCcw } from "lucide-react";
import { useMemo } from "react";

import { ApiKeysScreen } from "@/components/screens/ApiKeysScreen";
import { BackupsScreen } from "@/components/screens/BackupsScreen";
import { CronjobsScreen } from "@/components/screens/CronjobsScreen";
import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { Button } from "@/components/ui/Button";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { type Locale, titleForLocale, useI18n } from "@/lib/I18nContext";

import { CircuitBreakerSettingsSection } from "./CircuitBreakerSettingsSection";
import { GatewaySettingsSection } from "./GatewaySettingsSection";
import {
  GeneralSettingsSection,
  ModelTestSettingsSection,
} from "./ProfileSettingsSections";
import { createSettingsTabs, SettingsNavigation } from "./SettingsNavigation";
import { useAccountSettings } from "./useAccountSettings";
import { useSettingsDraft } from "./useSettingsDraft";

type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

function SettingsHeaderActions({
  locale,
  settings,
}: {
  locale: Locale;
  settings: SettingsDraftController;
}) {
  const refreshLabel = titleForLocale(locale, "刷新", "Refresh");

  return (
    <DashboardHeaderActions>
      <div className="flex items-center justify-end gap-2">
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

  return (
    <>
      <SettingsHeaderActions locale={locale} settings={settings} />
      <section className="mx-auto min-w-0 max-w-[1230px]">
        <h1 className="mb-5 px-1 text-xl font-semibold tracking-normal text-foreground xl:text-2xl">
          {titleForLocale(locale, "设置", "Settings")}
        </h1>
        <Tabs
          defaultValue="general"
          orientation="vertical"
          className="grid min-w-0 gap-8 lg:grid-cols-[220px_minmax(0,1fr)] lg:items-start"
        >
          <SettingsNavigation tabs={settingsTabs} />
          <div className="min-w-0">
            <GeneralSettingsSection
              locale={locale}
              settings={settings}
              account={account}
            />
            <GatewaySettingsSection locale={locale} settings={settings} />
            <ModelTestSettingsSection locale={locale} settings={settings} />
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
