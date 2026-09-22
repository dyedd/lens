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
      title={titleForLocale(locale, "导出备份", "Export backup")}
      actions={
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none"
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
      <p className="text-xs leading-5 text-muted-foreground">
        {titleForLocale(
          locale,
          "始终包含：系统设置、渠道与凭据、模型组、模型价格、定时任务和统计",
          "Always included: settings, channels and credentials, model groups, prices, cron jobs, and stats",
        )}
      </p>
      <SettingsFieldList>
        <SettingsFieldRow
          htmlFor="config-export-logs"
          title={titleForLocale(locale, "包含请求日志", "Include request logs")}
          description={titleForLocale(
            locale,
            "导出所有请求日志明细，文件体积可能明显增大",
            "Export all request log details; this can increase file size significantly",
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
          title={titleForLocale(
            locale,
            "包含网关 API Key",
            "Include gateway API keys",
          )}
          description={titleForLocale(
            locale,
            "会把网关鉴权 Key 一并写入备份，导出后请妥善保管",
            "Gateway auth keys will be included in the backup; keep the file secure",
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
