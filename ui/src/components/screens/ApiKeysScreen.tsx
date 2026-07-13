"use client";

import { GatewayApiKeyManager } from "@/components/settings/GatewayApiKeyManager";
import { useI18n } from "@/lib/I18nContext";

/** Render the gateway API key management screen. */
export function ApiKeysScreen() {
  const { locale } = useI18n();

  return (
    <section className="flex min-w-0 flex-col gap-4">
      <div className="flex min-w-0 flex-col gap-6">
        <GatewayApiKeyManager locale={locale} />
      </div>
    </section>
  );
}
