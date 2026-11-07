import { useQueryClient } from "@tanstack/react-query";
import { FileJson, Upload } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { SettingsSection } from "@/components/settings/settingsLayout";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { type ConfigImportResult, importConfigBackup } from "@/lib/api/backups";
import { getApiErrorMessage } from "@/lib/api/client";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import type { ConfigBackupPreview } from "./backupPreview";
import { parseBackupPreview, resultLabelForLocale } from "./backupPreview";
import { ConfigImportConfirmDialog } from "./ConfigImportConfirmDialog";
import { ConfigImportPreview } from "./ConfigImportPreview";
import { ConfigImportResultSummary } from "./ConfigImportResult";

export function ConfigImportCard({ locale }: { locale: Locale }) {
  const queryClient = useQueryClient();
  const timeZone = useAppTimeZone();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previewRequestId = useRef(0);
  const [isPreviewPending, setIsPreviewPending] = useState(false);

  const [isImporting, setIsImporting] = useState(false);
  const [confirmImportOpen, setConfirmImportOpen] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ConfigBackupPreview | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [importResult, setImportResult] = useState<ConfigImportResult | null>(
    null,
  );

  const previewSections = useMemo(() => {
    if (!preview) {
      return [];
    }
    const items = [
      {
        key: "settings",
        label: titleForLocale(locale, "系统设置", "System settings"),
        count: preview.counts.settings,
      },
      {
        key: "sites",
        label: titleForLocale(locale, "渠道", "Channels"),
        count: preview.counts.sites,
      },
      {
        key: "groups",
        label: titleForLocale(locale, "模型组", "Model groups"),
        count: preview.counts.groups,
      },
      {
        key: "model_prices",
        label: titleForLocale(locale, "模型价格", "Model prices"),
        count: preview.counts.model_prices,
      },
      {
        key: "cronjobs",
        label: titleForLocale(locale, "计划任务", "Scheduled tasks"),
        count: preview.counts.cronjobs,
      },
      {
        key: "stats",
        label: titleForLocale(locale, "统计数据", "Stats"),
        count: preview.counts.stats,
      },
    ];
    if (preview.include_gateway_api_keys) {
      items.push({
        key: "gateway_api_keys",
        label: titleForLocale(locale, "网关密钥", "Gateway keys"),
        count: preview.counts.gateway_api_keys,
      });
    }
    if (preview.include_request_logs) {
      items.push({
        key: "request_logs",
        label: titleForLocale(locale, "请求日志", "Request logs"),
        count: preview.counts.request_logs,
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
    const requestId = ++previewRequestId.current;
    setSelectedFile(file);
    setConfirmImportOpen(false);
    setImportResult(null);
    setPreview(null);
    setPreviewError("");
    setIsPreviewPending(Boolean(file));

    if (!file) {
      return;
    }

    try {
      const rawValue = await file.text();
      if (requestId !== previewRequestId.current) return;
      const nextPreview = parseBackupPreview(rawValue);
      setPreview(nextPreview);
    } catch {
      if (requestId === previewRequestId.current) {
        setPreviewError(
          titleForLocale(locale, "备份文件格式无效", "Invalid backup file"),
        );
      }
    } finally {
      if (requestId === previewRequestId.current) setIsPreviewPending(false);
    }
  }

  async function handleImport() {
    if (!selectedFile || !preview || isPreviewPending) {
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
      <SettingsSection
        title={titleForLocale(locale, "配置导入", "Import Configuration")}
        actions={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 px-2 text-sm text-muted-foreground shadow-none"
            disabled={!preview || isPreviewPending || isImporting}
            onClick={() => setConfirmImportOpen(true)}
          >
            {isImporting ? (
              <Spinner className="size-3.5" />
            ) : (
              <Upload className="size-3.5" />
            )}
            {isImporting
              ? titleForLocale(locale, "导入中...", "Importing...")
              : titleForLocale(locale, "导入并覆盖", "Import and overwrite")}
          </Button>
        }
      >
        <div className="space-y-3">
          <Input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            disabled={isImporting}
            onChange={(event) =>
              void handleFileChange(event.target.files?.[0] ?? null)
            }
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 px-2 text-sm shadow-none"
            disabled={isImporting}
            onClick={() => fileInputRef.current?.click()}
          >
            {isPreviewPending ? (
              <Spinner className="size-3.5" />
            ) : (
              <FileJson className="size-3.5" />
            )}
            {titleForLocale(locale, "选择 JSON 文件", "Select JSON file")}
          </Button>

          <ConfigImportPreview
            selectedFile={selectedFile}
            preview={preview}
            previewError={previewError}
            isPreviewPending={isPreviewPending}
            previewSections={previewSections}
            locale={locale}
            timeZone={timeZone}
          />

          <ConfigImportResultSummary rows={rowsAffectedList} locale={locale} />
        </div>
      </SettingsSection>

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
