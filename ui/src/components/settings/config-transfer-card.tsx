"use client"

import { useMemo, useRef, useState, useTransition } from "react"
import {
  CircleAlert,
  Database,
  Download,
  FileJson,
  KeyRound,
  ScrollText,
  Settings2,
  Upload,
  Waypoints,
} from "lucide-react"
import { useQueryClient } from "@tanstack/react-query"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Item,
  ItemContent,
  ItemGroup,
  ItemHeader,
  ItemTitle,
} from "@/components/ui/item"
import { Switch } from "@/components/ui/switch"
import { useToast } from "@/components/ui/toast"
import {
  ApiError,
  type ConfigBackupDump,
  type ConfigBackupStatsSnapshot,
  type ConfigImportResult,
  downloadConfigBackup,
  importConfigBackup,
} from "@/lib/api"
import { type Locale } from "@/lib/i18n"
import { cn } from "@/lib/utils"

function titleForLocale(locale: Locale, zh: string, en: string) {
  return locale === "zh-CN" ? zh : en
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

function parseStatsPreview(value: unknown): ConfigBackupStatsSnapshot {
  if (!isRecord(value)) {
    return {
      imported_total: null,
      imported_daily: [],
      request_daily: [],
      model_daily: [],
    }
  }

  return {
    imported_total: isRecord(value.imported_total)
      ? (value.imported_total as ConfigBackupStatsSnapshot["imported_total"])
      : null,
    imported_daily: Array.isArray(value.imported_daily) ? value.imported_daily : [],
    request_daily: Array.isArray(value.request_daily) ? value.request_daily : [],
    model_daily: Array.isArray(value.model_daily) ? value.model_daily : [],
  }
}

function parseBackupPreview(rawValue: string): ConfigBackupDump {
  const payload = JSON.parse(rawValue)
  if (!isRecord(payload)) {
    throw new Error("Invalid backup file")
  }

  return {
    version: typeof payload.version === "number" ? payload.version : 0,
    exported_at:
      typeof payload.exported_at === "string" ? payload.exported_at : "",
    lens_version:
      typeof payload.lens_version === "string" ? payload.lens_version : "",
    include_request_logs: Boolean(payload.include_request_logs),
    include_gateway_api_keys: Boolean(payload.include_gateway_api_keys),
    settings: Array.isArray(payload.settings) ? payload.settings : [],
    sites: Array.isArray(payload.sites) ? payload.sites : [],
    groups: Array.isArray(payload.groups) ? payload.groups : [],
    model_prices: Array.isArray(payload.model_prices)
      ? payload.model_prices
      : [],
    stats: parseStatsPreview(payload.stats),
    gateway_api_keys: Array.isArray(payload.gateway_api_keys)
      ? payload.gateway_api_keys
      : [],
    request_logs: Array.isArray(payload.request_logs) ? payload.request_logs : [],
  }
}

function formatExportedAt(value: string, locale: Locale) {
  if (!value) {
    return "n/a"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString(locale === "zh-CN" ? "zh-CN" : "en-US")
}

function resultLabelForLocale(locale: Locale, key: string) {
  const labels: Record<string, [string, string]> = {
    gateway_api_keys: ["网关 API Key", "Gateway API keys"],
    groups: ["模型组", "Model groups"],
    imported_stats_daily: ["导入统计(日)", "Imported stats (daily)"],
    imported_stats_total: ["导入统计(总计)", "Imported stats (total)"],
    model_group_items: ["模型组成员", "Model group items"],
    model_groups: ["模型组", "Model groups"],
    model_prices: ["模型价格", "Model prices"],
    overview_model_daily_stats: ["模型统计(日)", "Model stats (daily)"],
    request_log_daily_stats: ["请求统计(日)", "Request stats (daily)"],
    request_logs: ["请求日志", "Request logs"],
    settings: ["系统设置", "Settings"],
    site_base_urls: ["渠道地址", "Channel base URLs"],
    site_credentials: ["上游凭据", "Upstream credentials"],
    site_models: ["发现模型", "Discovered models"],
    site_protocol_bindings: ["渠道凭据绑定", "Channel credential bindings"],
    site_protocol_configs: ["渠道协议配置", "Channel protocol configs"],
    sites: ["渠道", "Channels"],
  }
  const label = labels[key]
  if (!label) {
    return key
  }
  return locale === "zh-CN" ? label[0] : label[1]
}

function PreviewMeta({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  )
}

export function ConfigTransferCard({ locale }: { locale: Locale }) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [isPreviewPending, startPreviewTransition] = useTransition()

  const [includeLogs, setIncludeLogs] = useState(false)
  const [includeGatewayApiKeys, setIncludeGatewayApiKeys] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [confirmImportOpen, setConfirmImportOpen] = useState(false)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ConfigBackupDump | null>(null)
  const [previewError, setPreviewError] = useState("")
  const [importResult, setImportResult] = useState<ConfigImportResult | null>(null)

  const alwaysIncludedItems = useMemo(
    () => [
      titleForLocale(locale, "系统设置", "Settings"),
      titleForLocale(locale, "渠道与上游凭据", "Channels & credentials"),
      titleForLocale(locale, "模型组配置", "Model groups"),
      titleForLocale(locale, "模型价格", "Model prices"),
      titleForLocale(locale, "统计数据", "Stats"),
    ],
    [locale]
  )

  const previewSections = useMemo(() => {
    if (!preview) {
      return []
    }
    const statsCount =
      (preview.stats.imported_total ? 1 : 0) +
      preview.stats.imported_daily.length +
      preview.stats.request_daily.length +
      preview.stats.model_daily.length
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
        key: "stats",
        label: titleForLocale(locale, "统计数据", "Stats"),
        count: statsCount,
      },
    ]
    if (preview.include_gateway_api_keys) {
      items.push({
        key: "gateway_api_keys",
        label: titleForLocale(locale, "网关 API Key", "Gateway API keys"),
        count: preview.gateway_api_keys.length,
      })
    }
    if (preview.include_request_logs) {
      items.push({
        key: "request_logs",
        label: titleForLocale(locale, "请求日志", "Request logs"),
        count: preview.request_logs.length,
      })
    }
    return items
  }, [locale, preview])

  const rowsAffectedList = useMemo(() => {
    const rowsAffected = importResult?.rows_affected
    if (!rowsAffected) {
      return []
    }
    return Object.entries(rowsAffected)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => ({
        key,
        label: resultLabelForLocale(locale, key),
        value,
      }))
  }, [importResult, locale])

  async function handleExport() {
    setIsExporting(true)
    try {
      const result = await downloadConfigBackup({
        includeLogs,
        includeGatewayApiKeys,
      })
      toast.success(
        titleForLocale(
          locale,
          `备份已导出: ${result.filename}`,
          `Backup exported: ${result.filename}`
        )
      )
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : titleForLocale(locale, "导出失败", "Failed to export backup")
      toast.error(message)
    } finally {
      setIsExporting(false)
    }
  }

  async function handleFileChange(file: File | null) {
    setSelectedFile(file)
    setImportResult(null)
    setPreview(null)
    setPreviewError("")

    if (!file) {
      return
    }

    try {
      const rawValue = await file.text()
      const nextPreview = parseBackupPreview(rawValue)
      startPreviewTransition(() => {
        setPreview(nextPreview)
      })
    } catch {
      startPreviewTransition(() => {
        setPreviewError(
          titleForLocale(locale, "备份文件格式无效", "Invalid backup file")
        )
      })
    }
  }

  async function handleImport() {
    if (!selectedFile) {
      return
    }

    setIsImporting(true)
    try {
      const result = await importConfigBackup(selectedFile)
      setImportResult(result)
      setConfirmImportOpen(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
      setSelectedFile(null)
      setPreview(null)
      setPreviewError("")
      await queryClient.invalidateQueries()
      toast.success(
        titleForLocale(locale, "备份已导入", "Backup imported")
      )
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : titleForLocale(locale, "导入失败", "Failed to import backup")
      toast.error(message)
    } finally {
      setIsImporting(false)
    }
  }

  return (
    <>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="py-0">
          <CardHeader className="px-5 pt-5 pb-0">
            <CardTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
              <Download className="size-4 text-muted-foreground" />
              <span>{titleForLocale(locale, "导出配置", "Export backup")}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 px-5 py-5">
            <div className="flex flex-wrap gap-2">
              {alwaysIncludedItems.map((item) => (
                <Badge key={item} variant="outline">
                  {item}
                </Badge>
              ))}
            </div>

            <FieldGroup>
              <Field orientation="horizontal" className="items-center justify-between">
                <div className="flex min-w-0 flex-col gap-1">
                  <FieldLabel className="w-auto">
                    {titleForLocale(locale, "包含请求日志", "Include request logs")}
                  </FieldLabel>
                  <FieldDescription>
                    {titleForLocale(
                      locale,
                      "导出所有请求日志明细，文件体积可能明显增大",
                      "Export all request log details; this can increase file size significantly"
                    )}
                  </FieldDescription>
                </div>
                <Switch
                  checked={includeLogs}
                  onCheckedChange={setIncludeLogs}
                />
              </Field>
              <Field orientation="horizontal" className="items-center justify-between">
                <div className="flex min-w-0 flex-col gap-1">
                  <FieldLabel className="w-auto">
                    {titleForLocale(locale, "包含网关 API Key", "Include gateway API keys")}
                  </FieldLabel>
                  <FieldDescription>
                    {titleForLocale(
                      locale,
                      "会把网关鉴权 Key 一并写入备份，导出后请妥善保管",
                      "Gateway auth keys will be included in the backup; keep the file secure"
                    )}
                  </FieldDescription>
                </div>
                <Switch
                  checked={includeGatewayApiKeys}
                  onCheckedChange={setIncludeGatewayApiKeys}
                />
              </Field>
            </FieldGroup>

            <div
              className={cn(
                "rounded-md border px-4 py-3 text-sm",
                includeLogs || includeGatewayApiKeys
                  ? "border-amber-200 bg-amber-50/70 text-amber-900"
                  : "bg-muted/30 text-muted-foreground"
              )}
            >
              <div className="flex items-center gap-2 font-medium">
                <CircleAlert className="size-4" />
                {titleForLocale(locale, "导出说明", "Export notes")}
              </div>
              <div className="mt-2 leading-6">
                {titleForLocale(
                  locale,
                  "渠道配置始终包含上游凭据，统计数据会一并备份；导出文件可直接用于新实例覆盖导入恢复。",
                  "Channel configuration always includes upstream credentials, and stats are backed up together; the exported file can be imported directly into a fresh instance."
                )}
              </div>
            </div>

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

        <Card className="py-0">
          <CardHeader className="px-5 pt-5 pb-0">
            <CardTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
              <Upload className="size-4 text-muted-foreground" />
              <span>{titleForLocale(locale, "导入配置", "Import backup")}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 px-5 py-5">
            <FieldGroup>
              <Field>
                <FieldLabel>
                  {titleForLocale(locale, "备份文件", "Backup file")}
                </FieldLabel>
                <Input
                  ref={fileInputRef}
                  type="file"
                  accept="application/json,.json"
                  onChange={(event) =>
                    void handleFileChange(event.target.files?.[0] ?? null)
                  }
                />
              </Field>
            </FieldGroup>

            {previewError ? (
              <div className="rounded-md border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {previewError}
              </div>
            ) : null}

            {selectedFile ? (
              <div className="rounded-md border bg-muted/20 px-4 py-3">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <FileJson className="size-4 text-muted-foreground" />
                  <span className="truncate">{selectedFile.name}</span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {Math.max(selectedFile.size / 1024, 0.1).toFixed(1)} KB
                </div>
              </div>
            ) : null}

            {preview ? (
              <div className="flex flex-col gap-3 rounded-lg border bg-muted/20 px-4 py-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <PreviewMeta
                    label={titleForLocale(locale, "版本", "Version")}
                    value={"v" + String(preview.version || 1)}
                  />
                  <PreviewMeta
                    label={titleForLocale(locale, "系统版本", "Lens version")}
                    value={preview.lens_version || "n/a"}
                  />
                  <PreviewMeta
                    label={titleForLocale(locale, "导出时间", "Exported at")}
                    value={formatExportedAt(preview.exported_at, locale)}
                  />
                </div>

                <ItemGroup className="gap-2">
                  {previewSections.map((item) => (
                    <Item key={item.key} variant="outline" size="sm">
                      <ItemContent>
                        <ItemHeader>
                          <ItemTitle>{item.label}</ItemTitle>
                          <Badge variant="secondary">{item.count}</Badge>
                        </ItemHeader>
                      </ItemContent>
                    </Item>
                  ))}
                </ItemGroup>
              </div>
            ) : selectedFile && isPreviewPending ? (
              <div className="rounded-md border bg-muted/20 px-4 py-6 text-sm text-muted-foreground">
                {titleForLocale(locale, "正在解析备份文件...", "Parsing backup file...")}
              </div>
            ) : null}

            <div className="rounded-md border border-destructive/15 bg-destructive/5 px-4 py-3 text-sm text-foreground">
              <div className="flex items-center gap-2 font-medium text-destructive">
                <CircleAlert className="size-4" />
                {titleForLocale(locale, "覆盖导入", "Overwrite import")}
              </div>
              <div className="mt-2 leading-6 text-muted-foreground">
                {titleForLocale(
                  locale,
                  "导入会替换现有渠道、模型组、设置、模型价格和统计数据；如果备份包包含日志或网关 API Key，也会一并覆盖。",
                  "Import replaces existing channels, model groups, settings, model prices, and stats. If the backup contains logs or gateway API keys, those sections are replaced as well."
                )}
              </div>
            </div>

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

            {rowsAffectedList.length ? (
              <div className="flex flex-col gap-3 rounded-lg border bg-muted/20 px-4 py-4">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Database className="size-4 text-muted-foreground" />
                  {titleForLocale(locale, "导入结果", "Import result")}
                </div>
                <ItemGroup className="gap-2">
                  {rowsAffectedList.map((item) => (
                    <Item key={item.key} variant="outline" size="sm">
                      <ItemContent>
                        <ItemHeader>
                          <ItemTitle className="font-medium">{item.label}</ItemTitle>
                          <Badge variant="secondary">{item.value}</Badge>
                        </ItemHeader>
                      </ItemContent>
                    </Item>
                  ))}
                </ItemGroup>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Dialog open={confirmImportOpen} onOpenChange={setConfirmImportOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {titleForLocale(locale, "确认导入备份", "Confirm backup import")}
            </DialogTitle>
            <DialogDescription>
              {titleForLocale(
                locale,
                "当前实例中的相关配置会被备份文件覆盖，请确认文件内容无误后继续。",
                "The related configuration in this instance will be overwritten by the backup file."
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-3">
            <div className="rounded-md border bg-muted/20 px-4 py-3">
              <div className="text-sm font-medium text-foreground">
                {selectedFile?.name ??
                  titleForLocale(locale, "未选择文件", "No file selected")}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {preview
                  ? titleForLocale(
                      locale,
                      `将覆盖 ${preview.sites.length} 个渠道、${preview.groups.length} 个模型组`,
                      `Will overwrite ${preview.sites.length} channels and ${preview.groups.length} model groups`
                    )
                  : titleForLocale(
                      locale,
                      "将按备份内容执行覆盖导入",
                      "Will perform an overwrite import based on the backup contents"
                    )}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">
                <Settings2 data-icon="inline-start" />
                {titleForLocale(locale, "设置", "Settings")}
              </Badge>
              <Badge variant="outline">
                <Waypoints data-icon="inline-start" />
                {titleForLocale(locale, "渠道", "Channels")}
              </Badge>
              <Badge variant="outline">
                <Database data-icon="inline-start" />
                {titleForLocale(locale, "模型组", "Model groups")}
              </Badge>
              <Badge variant="outline">
                <Database data-icon="inline-start" />
                {titleForLocale(locale, "统计数据", "Stats")}
              </Badge>
              {preview?.include_gateway_api_keys ? (
                <Badge variant="outline">
                  <KeyRound data-icon="inline-start" />
                  {titleForLocale(locale, "网关 API Key", "Gateway API keys")}
                </Badge>
              ) : null}
              {preview?.include_request_logs ? (
                <Badge variant="outline">
                  <ScrollText data-icon="inline-start" />
                  {titleForLocale(locale, "请求日志", "Request logs")}
                </Badge>
              ) : null}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmImportOpen(false)}
              disabled={isImporting}
            >
              {titleForLocale(locale, "取消", "Cancel")}
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => void handleImport()}
              disabled={isImporting}
            >
              <Upload data-icon="inline-start" />
              {isImporting
                ? titleForLocale(locale, "导入中...", "Importing...")
                : titleForLocale(locale, "确认覆盖导入", "Confirm import")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
