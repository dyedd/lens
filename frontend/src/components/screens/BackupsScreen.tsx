import { ConfigTransferCard } from "@/components/settings/ConfigTransferCard";
import { useI18n } from "@/lib/I18nContext";

/** Render configuration backup import and export controls. */
export function BackupsScreen() {
  const { locale } = useI18n();
  return <ConfigTransferCard locale={locale} />;
}
