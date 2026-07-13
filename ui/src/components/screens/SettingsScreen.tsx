"use client";

import { useMemo } from "react";
import { RotateCcw, Save } from "lucide-react";

import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { Button } from "@/components/ui/Button";
import { Tabs } from "@/components/ui/Tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { titleForLocale, useI18n, type Locale } from "@/lib/I18nContext";

import { CircuitBreakerSettingsSection } from "./settings/CircuitBreakerSettingsSection";
import { GatewaySettingsSection } from "./settings/GatewaySettingsSection";
import {
  AccountSettingsSection,
  AppearanceSettingsSection,
  ModelTestSettingsSection,
  TimeSettingsSection,
} from "./settings/ProfileSettingsSections";
import {
  createSettingsTabs,
  SettingsNavigation,
} from "./settings/SettingsNavigation";
import { useAccountSettings } from "./settings/useAccountSettings";
import { useSettingsDraft } from "./settings/useSettingsDraft";

type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

function SettingsHeaderActions({
  locale,
  settings,
}: {
  locale: Locale;
  settings: SettingsDraftController;
}) {
  const refreshLabel = titleForLocale(locale, "刷新", "Refresh");
  const saveSettingsLabel = settings.isSaving
    ? titleForLocale(locale, "保存中...", "Saving...")
    : titleForLocale(locale, "保存设置", "Save settings");

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
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={saveSettingsLabel}
              disabled={settings.isSaving || !settings.isSettingsReady}
              onClick={() => void settings.submitSettings()}
            >
              <Save data-icon="inline-start" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" align="end">
            {saveSettingsLabel}
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
      <section className="min-w-0">
        <Tabs
          defaultValue="appearance"
          orientation="vertical"
          className="grid min-w-0 gap-6 lg:grid-cols-[220px_minmax(0,760px)] lg:items-start"
        >
          <SettingsNavigation tabs={settingsTabs} />
          <div className="min-w-0">
            <AppearanceSettingsSection
              locale={locale}
              description={settingsTabs[0]!.description}
              settings={settings}
            />
            <AccountSettingsSection
              locale={locale}
              description={settingsTabs[1]!.description}
              account={account}
            />
            <TimeSettingsSection
              locale={locale}
              description={settingsTabs[2]!.description}
              settings={settings}
            />
            <GatewaySettingsSection
              locale={locale}
              description={settingsTabs[3]!.description}
              settings={settings}
            />
            <ModelTestSettingsSection
              locale={locale}
              description={settingsTabs[4]!.description}
              settings={settings}
            />
            <CircuitBreakerSettingsSection
              locale={locale}
              description={settingsTabs[5]!.description}
              settings={settings}
            />
          </div>
        </Tabs>
      </section>
    </>
  );
}
