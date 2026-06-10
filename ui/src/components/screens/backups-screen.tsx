"use client";

import { ConfigTransferCard } from "@/components/settings/config-transfer-card";
import { useI18n } from "@/lib/i18n";

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
