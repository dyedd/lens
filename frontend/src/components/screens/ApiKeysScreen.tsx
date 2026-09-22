import { GatewayApiKeyManager } from "@/components/settings/GatewayApiKeyManager";
import { useI18n } from "@/lib/I18nContext";

/** Render the gateway API key management screen. */
export function ApiKeysScreen() {
  const { locale } = useI18n();
  return <GatewayApiKeyManager locale={locale} />;
}
