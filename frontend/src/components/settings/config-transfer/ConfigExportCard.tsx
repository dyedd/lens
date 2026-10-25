import { Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import {
  SettingsFieldList,
  SettingsFieldRow,
  SettingsSection,
} from "@/components/settings/settingsLayout";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { Switch } from "@/components/ui/Switch";
import { downloadConfigBackup } from "@/lib/api/backups";
import { getApiErrorMessage } from "@/lib/api/client";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

export function ConfigExportCard({ locale }: { locale: Locale }) {
  const [shouldIncludeLogs, setShouldIncludeLogs] = useState(false);
  const [shouldIncludeGatewayApiKeys, setShouldIncludeGatewayApiKeys] =
    useState(false);
  const [isExporting, setIsExporting] = useState(false);

  async function handleExport() {
    setIsExporting(true);
    try {
      const result = await downloadConfigBackup({
        shouldIncludeLogs,
        shouldIncludeGatewayApiKeys,
      });
      toast.success(
        titleForLocale(
          locale,
          `备份已导出: ${result.filename}`,
          `Backup exported: ${result.filename}`,
        ),
      );
    } catch (error) {
      const message = getApiErrorMessage(
        error,
        titleForLocale(locale, "导出失败", "Failed to export backup"),
      );
      toast.error(message);
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <SettingsSection
      title={titleForLocale(locale, "配置归档", "Configuration Archive")}
      actions={
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 text-sm text-muted-foreground shadow-none"
          onClick={() => void handleExport()}
          disabled={isExporting}
        >
          {isExporting ? (
            <Spinner className="size-3.5" />
          ) : (
            <Download className="size-3.5" />
          )}
          {isExporting
            ? titleForLocale(locale, "导出中...", "Exporting...")
            : titleForLocale(locale, "导出 JSON", "Export JSON")}
        </Button>
      }
    >
      <SettingsFieldList>
        <SettingsFieldRow
          htmlFor="config-export-logs"
          title={titleForLocale(locale, "包含请求日志", "Include request logs")}
          description={titleForLocale(
            locale,
            "日志明细可能较大",
            "Log details may make the file large",
          )}
        >
          <Switch
            id="config-export-logs"
            checked={shouldIncludeLogs}
            onCheckedChange={setShouldIncludeLogs}
          />
        </SettingsFieldRow>
        <SettingsFieldRow
          htmlFor="config-export-api-keys"
          title={titleForLocale(locale, "包含网关密钥", "Include gateway keys")}
          description={titleForLocale(
            locale,
            "包含鉴权 Key，请妥善保管",
            "Includes auth keys; keep the file secure",
          )}
        >
          <Switch
            id="config-export-api-keys"
            checked={shouldIncludeGatewayApiKeys}
            onCheckedChange={setShouldIncludeGatewayApiKeys}
          />
        </SettingsFieldRow>
      </SettingsFieldList>
    </SettingsSection>
  );
}
