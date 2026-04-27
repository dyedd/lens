"use client"

import { GatewayApiKeyManager } from "@/components/settings/gateway-api-key-manager"
import { useI18n } from "@/lib/i18n"

export function ApiKeysScreen() {
  const { locale, t } = useI18n()

  return (
    <section className="flex min-w-0 flex-col gap-4">
      <div className="flex min-w-0 flex-col gap-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <h1 className="text-xl font-semibold text-foreground">{t.apiKeys}</h1>
        </div>
        <GatewayApiKeyManager locale={locale} />
      </div>
    </section>
  )
}
