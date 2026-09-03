import type { Locale } from "@/lib/I18nContext";
import { ConfigExportCard } from "./config-transfer/ConfigExportCard";
import { ConfigImportCard } from "./config-transfer/ConfigImportCard";
import { ForeignImportCard } from "./config-transfer/ForeignImportCard";

/** Renders backup export, destructive restore, and foreign channel migration. */
export function ConfigTransferCard({ locale }: { locale: Locale }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 xl:grid-cols-12">
        <div className="xl:col-span-5">
          <ConfigExportCard locale={locale} />
        </div>
        <div className="xl:col-span-7">
          <ConfigImportCard locale={locale} />
        </div>
      </div>
      <ForeignImportCard locale={locale} />
    </div>
  );
}
