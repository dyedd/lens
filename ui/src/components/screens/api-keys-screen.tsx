"use client";

import { GatewayApiKeyManager } from "@/components/settings/gateway-api-key-manager";
import { useI18n } from "@/lib/i18n";

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
