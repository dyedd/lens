"use client"

import { ConfigTransferCard } from "@/components/settings/config-transfer-card"
import { useI18n } from "@/lib/i18n"

export function BackupsScreen() {
  const { locale, t } = useI18n()

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <h1 className="text-xl font-semibold text-foreground">{t.backups}</h1>
        </div>
        <ConfigTransferCard locale={locale} />
      </div>
    </section>
  )
}
