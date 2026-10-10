import { CircleAlert, Download, FileUp, RotateCcw, Upload } from "lucide-react";
import { type ChangeEvent, type DragEvent, useRef, useState } from "react";
import { useForeignImport } from "@/components/settings/config-transfer/useForeignImport";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Spinner } from "@/components/ui/Spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { Textarea } from "@/components/ui/Textarea";
import type { ForeignSiteFormat } from "@/lib/api/foreignImports";
import type { SiteBatchImportResult } from "@/lib/api/sites";
import { protocolLabel } from "@/lib/protocols";
import { importReasonLabel, importStatusLabel } from "./channelBatchImport";
import type { Locale } from "./channelTypes";

const FORMAT_LABELS: Record<ForeignSiteFormat, [string, string]> = {
  lens: ["Lens 备份", "Lens backup"],
  metapi: ["Metapi", "Metapi"],
  sub2api: ["Sub2API", "Sub2API"],
  ccload: ["ccLoad", "ccLoad"],
  all_api_hub: ["All API Hub", "All API Hub"],
  octopus: ["Octopus", "Octopus"],
  cli_proxy_api: ["CLIProxyAPI", "CLIProxyAPI"],
};

/** Renders the channel batch-import workflow and its validation results. */
export function BatchImportDialog({
  open,
  onOpenChange,
  locale,
  importText,
  importError,
  importResult,
  importing,
  onTextChange,
  onFileChange,
  onDownloadTemplate,
  onImport,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  locale: Locale;
  importText: string;
  importError: string;
  importResult: SiteBatchImportResult | null;
  importing: boolean;
  onTextChange: (value: string) => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onDownloadTemplate: () => void;
  onImport: () => void;
}) {
  const isZh = locale === "zh-CN";
  const [tab, setTab] = useState<"standard" | "foreign">("standard");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const foreignFileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const foreign = useForeignImport(locale);
  const resultRows = importResult?.items ?? [];

  function handleForeignDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(false);
    const droppedFile = event.dataTransfer.files?.[0];
    if (droppedFile) {
      void foreign.loadFile(droppedFile);
    }
  }

  const isBusy = importing || foreign.isImporting || foreign.isPreviewing;

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (isBusy) return;
        onOpenChange(nextOpen);
      }}
    >
      {open ? (
        <AppDialogContent
          className="max-w-3xl"
          title={isZh ? "导入渠道" : "Import channels"}
          footer={
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onOpenChange(false)}
                disabled={isBusy}
              >
                {isZh ? "取消" : "Cancel"}
              </Button>
              {tab === "standard" ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={onImport}
                  disabled={importing}
                >
                  {importing
                    ? isZh
                      ? "导入中..."
                      : "Importing..."
                    : isZh
                      ? "导入"
                      : "Import"}
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void foreign.importSelected()}
                  disabled={
                    foreign.isImporting ||
                    !foreign.preview ||
                    foreign.selectedIndexes.size === 0
                  }
                >
                  {foreign.isImporting
                    ? isZh
                      ? "导入中..."
                      : "Importing..."
                    : isZh
                      ? `导入选中的 ${foreign.selectedIndexes.size} 项`
                      : `Import ${foreign.selectedIndexes.size} selected`}
                </Button>
              )}
            </>
          }
        >
          <div className="grid gap-4">
            <div className="flex items-center justify-between pb-1">
              <SegmentedControl
                value={tab}
                onValueChange={(val) => setTab(val as "standard" | "foreign")}
                options={[
                  {
                    value: "standard",
                    label: isZh ? "标准 JSON / 模板" : "JSON / Template",
                  },
                  {
                    value: "foreign",
                    label: isZh
                      ? "第三方一键迁移 (One API / Sub2API 等)"
                      : "Migrate from other tools",
                  },
                ]}
              />
            </div>

            {tab === "standard" ? (
              <div className="grid gap-4">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={onFileChange}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={importing}
                  >
                    <Upload data-icon="inline-start" />
                    {isZh ? "选择 JSON 文件" : "Choose JSON"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onDownloadTemplate}
                    disabled={importing}
                  >
                    <Download data-icon="inline-start" />
                    {isZh ? "下载导入模板" : "Download template"}
                  </Button>
                </div>

                <FieldGroup>
                  <Field data-invalid={Boolean(importError)}>
                    <FieldLabel htmlFor="channels-batch-import-json" required>
                      {isZh ? "JSON 内容" : "JSON"}
                    </FieldLabel>
                    <Textarea
                      id="channels-batch-import-json"
                      value={importText}
                      onChange={(event) => onTextChange(event.target.value)}
                      className="min-h-[220px] font-mono text-xs"
                      spellCheck={false}
                      aria-invalid={Boolean(importError)}
                      disabled={importing}
                    />
                    {importError ? (
                      <FieldDescription className="text-destructive">
                        {importError}
                      </FieldDescription>
                    ) : null}
                  </Field>
                </FieldGroup>

                {importResult ? (
                  <div className="grid gap-3">
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <ImportSummaryMetric
                        label={isZh ? "创建" : "Created"}
                        value={importResult.created_count}
                      />
                      <ImportSummaryMetric
                        label={isZh ? "跳过" : "Skipped"}
                        value={importResult.skipped_count}
                      />
                      <ImportSummaryMetric
                        label={isZh ? "错误" : "Errors"}
                        value={importResult.error_count}
                      />
                      <ImportSummaryMetric
                        label={isZh ? "未提交" : "Not committed"}
                        value={importResult.not_committed_count}
                      />
                    </div>

                    {resultRows.length ? (
                      <div className="max-h-56 overflow-y-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead className="w-16">
                                {isZh ? "序号" : "Index"}
                              </TableHead>
                              <TableHead>{isZh ? "渠道" : "Channel"}</TableHead>
                              <TableHead className="w-24">
                                {isZh ? "状态" : "Status"}
                              </TableHead>
                              <TableHead>{isZh ? "原因" : "Reason"}</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {resultRows.map((row) => {
                              const reason = row.errors.length
                                ? row.errors
                                    .map(
                                      (error) =>
                                        `${error.field}: ${error.message}`,
                                    )
                                    .join("; ")
                                : importReasonLabel(row.reason, locale);
                              return (
                                <TableRow key={`${row.index}-${row.status}`}>
                                  <TableCell>{row.index + 1}</TableCell>
                                  <TableCell className="max-w-[180px] break-words">
                                    {row.name}
                                  </TableCell>
                                  <TableCell>
                                    <Badge variant="secondary">
                                      {importStatusLabel(row.status, locale)}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="max-w-[320px] whitespace-normal break-words">
                                    {reason || "-"}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs leading-5 text-muted-foreground">
                  {isZh
                    ? "智能识别 Octopus、CLIProxyAPI、metapi、Sub2API、ccLoad、All API Hub 导出的 JSON、YAML 或 CSV 格式。"
                    : "Supports JSON, YAML, or CSV exports from Octopus, CLIProxyAPI, metapi, Sub2API, ccLoad, and All API Hub."}
                </p>

                <input
                  ref={foreignFileInputRef}
                  type="file"
                  accept=".json,.yaml,.yml,.csv,application/json,application/yaml,text/csv"
                  className="hidden"
                  onChange={(event) => {
                    void foreign.loadFile(event.target.files?.[0] ?? null);
                    event.target.value = "";
                  }}
                />

                {!foreign.preview ? (
                  <button
                    type="button"
                    onClick={() => foreignFileInputRef.current?.click()}
                    disabled={foreign.isPreviewing}
                    onDragOver={(event) => {
                      event.preventDefault();
                      setIsDragging(true);
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleForeignDrop}
                    className={`flex w-full flex-col items-center gap-2 rounded-lg border border-dashed border-border/80 bg-muted/20 px-4 py-10 text-center outline-none transition-colors hover:bg-muted/40 ${
                      isDragging ? "bg-muted ring-2 ring-primary" : ""
                    }`}
                  >
                    {foreign.isPreviewing ? (
                      <Spinner className="size-5" />
                    ) : (
                      <FileUp className="size-6 text-muted-foreground" />
                    )}
                    <span className="text-sm font-medium">
                      {foreign.isPreviewing
                        ? isZh
                          ? "正在识别解析文件..."
                          : "Recognizing file..."
                        : isZh
                          ? "点击选择导出文件，或直接拖拽到此处"
                          : "Choose export file or drop it here"}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      .json, .yaml, .csv
                    </span>
                  </button>
                ) : (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/30 p-2.5">
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">
                          {FORMAT_LABELS[foreign.preview.format]?.[
                            isZh ? 0 : 1
                          ] ?? foreign.preview.format}
                        </Badge>
                        <span className="truncate text-xs font-medium text-foreground">
                          {foreign.file?.name}
                        </span>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="xs"
                        onClick={() => foreignFileInputRef.current?.click()}
                      >
                        <RotateCcw className="size-3" />
                        {isZh ? "更换文件" : "Change file"}
                      </Button>
                    </div>

                    {foreign.preview.warnings.length > 0 ? (
                      <div className="flex flex-col gap-1">
                        {foreign.preview.warnings.map((warning) => (
                          <p
                            key={warning}
                            className="flex items-start gap-1.5 text-xs text-muted-foreground"
                          >
                            <CircleAlert className="mt-0.5 size-3.5 shrink-0" />
                            {warning}
                          </p>
                        ))}
                      </div>
                    ) : null}

                    {foreign.preview.sites.length > 0 ? (
                      <div className="flex flex-col">
                        <div className="flex items-center justify-between pb-1">
                          <span className="text-xs text-muted-foreground">
                            {isZh
                              ? `识别到 ${foreign.preview.sites.length} 个渠道，已选 ${foreign.selectedIndexes.size} 项`
                              : `Recognized ${foreign.preview.sites.length} channels (${foreign.selectedIndexes.size} selected)`}
                          </span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs"
                            onClick={foreign.toggleAllSites}
                          >
                            {foreign.selectedIndexes.size ===
                            foreign.preview.sites.length
                              ? isZh
                                ? "全不选"
                                : "Deselect all"
                              : isZh
                                ? "全选"
                                : "Select all"}
                          </Button>
                        </div>
                        <div className="max-h-72 divide-y divide-border/40 overflow-y-auto rounded-md border border-border/60 bg-background px-3">
                          {foreign.preview.sites.map((site, index) => {
                            const checkboxId = `foreign-dialog-site-${index}`;
                            return (
                              <label
                                key={checkboxId}
                                htmlFor={checkboxId}
                                className="flex cursor-pointer items-center gap-3 py-2"
                              >
                                <Checkbox
                                  id={checkboxId}
                                  checked={foreign.selectedIndexes.has(index)}
                                  onCheckedChange={() =>
                                    foreign.toggleSite(index)
                                  }
                                />
                                <span className="flex min-w-0 flex-1 flex-col">
                                  <span className="truncate text-xs font-medium text-foreground">
                                    {site.name}
                                    {!site.enabled && (
                                      <span className="ml-2 text-xs font-normal text-muted-foreground">
                                        {isZh ? "已停用" : "Disabled"}
                                      </span>
                                    )}
                                  </span>
                                  <span className="truncate text-[11px] text-muted-foreground">
                                    {site.base_urls[0] ?? ""}
                                  </span>
                                </span>
                                <span className="hidden shrink-0 items-center gap-1 sm:flex">
                                  {site.protocols.map((protocol) => (
                                    <Badge
                                      key={protocol}
                                      variant="secondary"
                                      className="text-[10px]"
                                    >
                                      {protocolLabel(protocol, locale)}
                                    </Badge>
                                  ))}
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}

                    {foreign.importResult ? (
                      <div className="grid gap-2 border-t border-border/60 pt-3">
                        <div className="text-xs font-medium">
                          {isZh ? "导入结果" : "Import result"}
                        </div>
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                          <ImportSummaryMetric
                            label={isZh ? "创建" : "Created"}
                            value={foreign.importResult.created_count}
                          />
                          <ImportSummaryMetric
                            label={isZh ? "跳过" : "Skipped"}
                            value={foreign.importResult.skipped_count}
                          />
                          <ImportSummaryMetric
                            label={isZh ? "错误" : "Errors"}
                            value={foreign.importResult.error_count}
                          />
                          <ImportSummaryMetric
                            label={isZh ? "未提交" : "Not committed"}
                            value={foreign.importResult.not_committed_count}
                          />
                        </div>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            )}
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}

export function ImportSummaryMetric({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-md bg-muted/35 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-base font-semibold text-foreground">{value}</div>
    </div>
  );
}
