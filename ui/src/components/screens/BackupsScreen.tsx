"use client";

import { ConfigTransferCard } from "@/components/settings/ConfigTransferCard";
import { useI18n } from "@/lib/I18nContext";

/** Render configuration backup import and export controls. */
export function BackupsScreen() {
  const { locale } = useI18n();

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-6">
        <ConfigTransferCard locale={locale} />
      </div>
    </section>
  );
}
