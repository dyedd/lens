"use client";

import { useMemo, useState } from "react";
import { CircleAlert, Download } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
import { Switch } from "@/components/ui/Switch";
import { downloadConfigBackup, getApiErrorMessage } from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

export function ConfigExportCard({ locale }: { locale: Locale }) {
  const [shouldIncludeLogs, setShouldIncludeLogs] = useState(false);
  const [shouldIncludeGatewayApiKeys, setShouldIncludeGatewayApiKeys] =
    useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const alwaysIncludedItems = useMemo(
    () => [
      titleForLocale(locale, "系统设置", "Settings"),
      titleForLocale(locale, "渠道与上游凭据", "Channels & credentials"),
      titleForLocale(locale, "模型组配置", "Model groups"),
      titleForLocale(locale, "模型价格", "Model prices"),
      titleForLocale(locale, "定时任务", "Cron jobs"),
      titleForLocale(locale, "统计数据", "Stats"),
    ],
    [locale],
  );

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
          <span>{titleForLocale(locale, "导出配置", "Export backup")}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 px-4 py-4 sm:px-5 sm:py-5">
        <div className="flex flex-wrap gap-2">
          {alwaysIncludedItems.map((item) => (
            <Badge key={item} variant="outline">
              {item}
            </Badge>
          ))}
        </div>

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

        <Alert>
          <CircleAlert />
          <AlertTitle>
            {titleForLocale(locale, "导出说明", "Export notes")}
          </AlertTitle>
          <AlertDescription>
            {titleForLocale(
              locale,
              "渠道配置始终包含上游凭据，统计数据会一并备份；导出文件可直接用于新实例覆盖导入恢复。",
              "Channel configuration always includes upstream credentials, and stats are backed up together; the exported file can be imported directly into a fresh instance.",
            )}
          </AlertDescription>
        </Alert>

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
