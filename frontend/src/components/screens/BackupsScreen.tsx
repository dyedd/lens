import { ConfigTransferCard } from "@/components/settings/ConfigTransferCard";
import { useI18n } from "@/lib/I18nContext";

export function BackupsScreen() {
  const { locale } = useI18n();
  return <ConfigTransferCard locale={locale} />;
}
