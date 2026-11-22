import {
  SettingsPage,
  SettingsSectionSeparator,
} from "@/components/ui/SettingsLayout";
import type { Locale } from "@/lib/I18nContext";
import { ConfigExportCard } from "./config-transfer/ConfigExportCard";
import { ConfigImportCard } from "./config-transfer/ConfigImportCard";
import { ForeignImportCard } from "./config-transfer/ForeignImportCard";

/** Renders backup export, restore, and foreign channel migration. */
export function ConfigTransferCard({ locale }: { locale: Locale }) {
  return (
    <SettingsPage>
      <ConfigExportCard locale={locale} />
      <SettingsSectionSeparator />
      <ConfigImportCard locale={locale} />
      <SettingsSectionSeparator />
      <ForeignImportCard locale={locale} />
    </SettingsPage>
  );
}
