import { Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
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
    <Card className="py-0">
      <CardHeader className="px-4 pt-4 pb-0 sm:px-5 sm:pt-5">
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Download className="size-4 text-muted-foreground" />
          <span>{titleForLocale(locale, "导出备份", "Export backup")}</span>
        </CardTitle>
        <CardDescription>
          {titleForLocale(
            locale,
            "把当前实例的完整配置打包为 JSON 文件。",
            "Package the full configuration of this instance as a JSON file.",
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 px-4 py-4 sm:px-5 sm:py-5">
        <p className="text-sm text-muted-foreground">
          {titleForLocale(
            locale,
            "始终包含：系统设置 · 渠道与凭据 · 模型组 · 模型价格 · 定时任务 · 统计",
            "Always included: settings · channels & credentials · model groups · prices · cron jobs · stats",
          )}
        </p>

        <FieldGroup>
          <Field
            orientation="horizontal"
            className="flex-wrap items-center justify-between"
          >
            <div className="flex min-w-0 flex-col gap-1">
              <FieldLabel className="w-auto">
                {titleForLocale(locale, "包含请求日志", "Include request logs")}
              </FieldLabel>
              <FieldDescription>
                {titleForLocale(
                  locale,
                  "导出所有请求日志明细，文件体积可能明显增大",
                  "Export all request log details; this can increase file size significantly",
                )}
              </FieldDescription>
            </div>
            <Switch
              checked={shouldIncludeLogs}
              onCheckedChange={setShouldIncludeLogs}
            />
          </Field>
          <Field
            orientation="horizontal"
            className="flex-wrap items-center justify-between"
          >
            <div className="flex min-w-0 flex-col gap-1">
              <FieldLabel className="w-auto">
                {titleForLocale(
                  locale,
                  "包含网关 API Key",
                  "Include gateway API keys",
                )}
              </FieldLabel>
              <FieldDescription>
                {titleForLocale(
                  locale,
                  "会把网关鉴权 Key 一并写入备份，导出后请妥善保管",
                  "Gateway auth keys will be included in the backup; keep the file secure",
                )}
              </FieldDescription>
            </div>
            <Switch
              checked={shouldIncludeGatewayApiKeys}
              onCheckedChange={setShouldIncludeGatewayApiKeys}
            />
          </Field>
        </FieldGroup>

        <Button
          type="button"
          onClick={() => void handleExport()}
          disabled={isExporting}
        >
          <Download data-icon="inline-start" />
          {isExporting
            ? titleForLocale(locale, "导出中...", "Exporting...")
            : titleForLocale(locale, "导出 JSON", "Export JSON")}
        </Button>
      </CardContent>
    </Card>
  );
}
