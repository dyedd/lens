import { GatewayApiKeyManager } from "@/components/settings/GatewayApiKeyManager";
import { useI18n } from "@/lib/I18nContext";

export function ApiKeysScreen() {
  const { locale } = useI18n();
  return <GatewayApiKeyManager locale={locale} />;
}
