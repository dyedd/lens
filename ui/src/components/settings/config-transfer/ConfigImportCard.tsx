"use client";

import { useMemo, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { CircleAlert, FileJson, Upload } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/Alert";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import {
  type ConfigBackupDump,
  type ConfigImportResult,
  getApiErrorMessage,
  importConfigBackup,
} from "@/lib/api";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { titleForLocale, type Locale } from "@/lib/I18nContext";
import { ConfigImportConfirmDialog } from "./ConfigImportConfirmDialog";
import { ConfigImportPreview } from "./ConfigImportPreview";
import { ConfigImportResultSummary } from "./ConfigImportResult";
import {
  parseBackupPreview,
  resultLabelForLocale,
} from "./configTransferUtils";

export function ConfigImportCard({ locale }: { locale: Locale }) {
  const queryClient = useQueryClient();
  const timeZone = useAppTimeZone();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isPreviewPending, startPreviewTransition] = useTransition();

  const [isImporting, setIsImporting] = useState(false);
  const [confirmImportOpen, setConfirmImportOpen] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ConfigBackupDump | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [importResult, setImportResult] = useState<ConfigImportResult | null>(
    null,
  );

  const previewSections = useMemo(() => {
    if (!preview) {
      return [];
    }
    const statsCount =
      (preview.stats.imported_total ? 1 : 0) +
      preview.stats.imported_daily.length +
      preview.stats.request_daily.length +
      preview.stats.model_daily.length;
    const items = [
      {
        key: "settings",
        label: titleForLocale(locale, "系统设置", "Settings"),
        count: preview.settings.length,
      },
      {
        key: "sites",
        label: titleForLocale(locale, "渠道", "Channels"),
        count: preview.sites.length,
      },
      {
        key: "groups",
        label: titleForLocale(locale, "模型组", "Model groups"),
        count: preview.groups.length,
      },
      {
        key: "model_prices",
        label: titleForLocale(locale, "模型价格", "Model prices"),
        count: preview.model_prices.length,
      },
      {
        key: "cronjobs",
        label: titleForLocale(locale, "定时任务", "Cron jobs"),
        count: preview.cronjobs.length,
      },
      {
        key: "stats",
        label: titleForLocale(locale, "统计数据", "Stats"),
        count: statsCount,
      },
    ];
    if (preview.include_gateway_api_keys) {
      items.push({
        key: "gateway_api_keys",
        label: titleForLocale(locale, "网关 API Key", "Gateway API keys"),
        count: preview.gateway_api_keys.length,
      });
    }
    if (preview.include_request_logs) {
      items.push({
        key: "request_logs",
        label: titleForLocale(locale, "请求日志", "Request logs"),
        count: preview.request_logs.length,
      });
    }
    return items;
  }, [locale, preview]);

  const rowsAffectedList = useMemo(() => {
    const rowsAffected = importResult?.rows_affected;
    if (!rowsAffected) {
      return [];
    }
    return Object.entries(rowsAffected)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => ({
        key,
        label: resultLabelForLocale(locale, key),
        value,
      }));
  }, [importResult, locale]);

  async function handleFileChange(file: File | null) {
    setSelectedFile(file);
    setImportResult(null);
    setPreview(null);
    setPreviewError("");

    if (!file) {
      return;
    }

    try {
      const rawValue = await file.text();
      const nextPreview = parseBackupPreview(rawValue);
      startPreviewTransition(() => {
        setPreview(nextPreview);
      });
    } catch {
      startPreviewTransition(() => {
        setPreviewError(
          titleForLocale(locale, "备份文件格式无效", "Invalid backup file"),
        );
      });
    }
  }

  async function handleImport() {
    if (!selectedFile) {
      return;
    }

    setIsImporting(true);
    try {
      const result = await importConfigBackup(selectedFile);
      setImportResult(result);
      setConfirmImportOpen(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      setSelectedFile(null);
      setPreview(null);
      setPreviewError("");
      await queryClient.invalidateQueries();
      toast.success(titleForLocale(locale, "备份已导入", "Backup imported"));
    } catch (error) {
      const message = getApiErrorMessage(
        error,
        titleForLocale(locale, "导入失败", "Failed to import backup"),
      );
      toast.error(message);
    } finally {
      setIsImporting(false);
    }
  }

  return (
    <>
      <Card className="py-0">
        <CardHeader className="px-4 pt-4 pb-0 sm:px-5 sm:pt-5">
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
            <Upload className="size-4 text-muted-foreground" />
            <span>{titleForLocale(locale, "导入配置", "Import backup")}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 px-4 py-4 sm:px-5 sm:py-5">
          <FieldGroup>
            <Field>
              <FieldLabel>
                {titleForLocale(locale, "备份文件", "Backup file")}
              </FieldLabel>
              <Input
                ref={fileInputRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(event) =>
                  void handleFileChange(event.target.files?.[0] ?? null)
                }
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
              >
                <FileJson data-icon="inline-start" />
                {titleForLocale(locale, "选择 JSON 文件", "Select JSON file")}
              </Button>
            </Field>
          </FieldGroup>

          <ConfigImportPreview
            selectedFile={selectedFile}
            preview={preview}
            previewError={previewError}
            isPreviewPending={isPreviewPending}
            previewSections={previewSections}
            locale={locale}
            timeZone={timeZone}
          />

          <Alert variant="destructive">
            <CircleAlert />
            <AlertTitle>
              {titleForLocale(locale, "覆盖导入", "Overwrite import")}
            </AlertTitle>
            <AlertDescription>
              {titleForLocale(
                locale,
                "导入会替换现有渠道、模型组、设置、模型价格、定时任务和统计数据；如果备份包包含日志或网关 API Key，也会一并覆盖。",
                "Import replaces existing channels, model groups, settings, model prices, cron jobs, and stats. If the backup contains logs or gateway API keys, those sections are replaced as well.",
              )}
            </AlertDescription>
          </Alert>

          <Button
            type="button"
            variant="outline"
            disabled={!selectedFile || Boolean(previewError) || isImporting}
            onClick={() => setConfirmImportOpen(true)}
          >
            <Upload data-icon="inline-start" />
            {isImporting
              ? titleForLocale(locale, "导入中...", "Importing...")
              : titleForLocale(locale, "导入并覆盖", "Import and overwrite")}
          </Button>

          <ConfigImportResultSummary rows={rowsAffectedList} locale={locale} />
        </CardContent>
      </Card>

      <ConfigImportConfirmDialog
        open={confirmImportOpen}
        onOpenChange={setConfirmImportOpen}
        selectedFile={selectedFile}
        preview={preview}
        isImporting={isImporting}
        locale={locale}
        onConfirm={() => void handleImport()}
      />
    </>
  );
}
