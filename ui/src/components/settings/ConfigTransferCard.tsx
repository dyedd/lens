"use client";

import { type Locale } from "@/lib/I18nContext";
import { ConfigExportCard } from "./config-transfer/ConfigExportCard";
import { ConfigImportCard } from "./config-transfer/ConfigImportCard";

/** Renders configuration backup export and import controls. */
export function ConfigTransferCard({ locale }: { locale: Locale }) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <ConfigExportCard locale={locale} />
      <ConfigImportCard locale={locale} />
    </div>
  );
}
