import { CircleAlert, FileInput, FileUp, RotateCcw } from "lucide-react";
import { type DragEvent, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import type { ForeignSiteFormat } from "@/lib/api/foreignImports";
import type { SiteBatchImportResult } from "@/lib/api/sites";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import { PROTOCOL_DOT_CLASS, protocolLabel } from "@/lib/protocols";
import { useForeignImport } from "./useForeignImport";

const FORMAT_LABELS: Record<ForeignSiteFormat, [string, string]> = {
  lens: ["Lens 备份", "Lens backup"],
  metapi: ["Metapi", "Metapi"],
  sub2api: ["Sub2API", "Sub2API"],
  ccload: ["ccLoad", "ccLoad"],
  all_api_hub: ["All API Hub", "All API Hub"],
  octopus: ["Octopus", "Octopus"],
  cli_proxy_api: ["CLIProxyAPI", "CLIProxyAPI"],
};

const SKIP_REASON_LABELS: Record<string, [string, string]> = {
  duplicate_name: ["名称已存在", "Name already exists"],
  duplicate_in_file: ["文件内重名", "Duplicate in file"],
  batch_validation_failed: ["批次校验未通过", "Batch validation failed"],
};

function formatLabel(locale: Locale, format: ForeignSiteFormat) {
  const [zh, en] = FORMAT_LABELS[format];
  return titleForLocale(locale, zh, en);
}

/** Render the foreign backup migration card: recognize, select, and add channels. */
export function ForeignImportCard({ locale }: { locale: Locale }) {
  const {
    file,
    preview,
    selectedIndexes,
    isPreviewing,
    isImporting,
    importResult,
    loadFile,
    toggleSite,
    toggleAllSites,
    importSelected,
  } = useForeignImport(locale);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const isReady = preview !== null;
  const selectedCount = selectedIndexes.size;

  function handleDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(false);
    const droppedFile = event.dataTransfer.files?.[0];
    if (droppedFile) {
      void loadFile(droppedFile);
    }
  }

  function importOutcomeReason(item: SiteBatchImportResult["items"][number]) {
    const reasonLabels = SKIP_REASON_LABELS[item.reason];
    return (
      item.errors[0]?.message ??
      (reasonLabels
        ? titleForLocale(locale, reasonLabels[0], reasonLabels[1])
        : item.reason)
    );
  }

  return (
    <Card className="py-0">
      <CardHeader className="px-4 pt-4 pb-0 sm:px-5 sm:pt-5">
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
          <FileInput className="size-4 text-muted-foreground" />
          <span>
            {titleForLocale(
              locale,
              "从其他项目导入渠道",
              "Import channels from other tools",
            )}
          </span>
        </CardTitle>
        <CardDescription>
          {titleForLocale(
            locale,
            "支持 Octopus、CLIProxyAPI、metapi、Sub2API、ccLoad、All API Hub 导出的 JSON、YAML 或 CSV；只追加渠道，不改动现有配置。",
            "Supports JSON, YAML, or CSV exports from Octopus, CLIProxyAPI, metapi, Sub2API, ccLoad, and All API Hub; only appends channels and leaves current configuration unchanged.",
          )}
        </CardDescription>
        <CardAction>
          {isReady && file ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              <RotateCcw data-icon="inline-start" />
              {titleForLocale(locale, "换一个文件", "Change file")}
            </Button>
          ) : null}
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 px-4 py-4 sm:px-5 sm:py-5">
        <input
          ref={fileInputRef}
          type="file"
          accept=".json,.yaml,.yml,.csv,application/json,application/yaml,text/csv"
          className="hidden"
          onChange={(event) => {
            void loadFile(event.target.files?.[0] ?? null);
            event.target.value = "";
          }}
        />

        {!isReady ? (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isPreviewing}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`flex w-full flex-col items-center gap-1.5 rounded-xl bg-muted/40 px-4 py-10 text-center outline-none transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-wait ${
              isDragging ? "bg-muted ring-2 ring-ring" : ""
            }`}
          >
            <FileUp className="size-5 text-muted-foreground" />
            <span className="text-sm font-medium">
              {isPreviewing
                ? titleForLocale(
                    locale,
                    "正在识别文件...",
                    "Recognizing file...",
                  )
                : titleForLocale(
                    locale,
                    "选择备份文件，或拖拽到此处",
                    "Choose a backup file, or drop it here",
                  )}
            </span>
          </button>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">
                {formatLabel(locale, preview.format)}
              </Badge>
              <span className="min-w-0 truncate text-sm text-foreground">
                {file?.name}
              </span>
              <span className="text-xs text-muted-foreground">
                {file
                  ? titleForLocale(
                      locale,
                      `${Math.max(file.size / 1024, 0.1).toFixed(1)} KB`,
                      `${Math.max(file.size / 1024, 0.1).toFixed(1)} KB`,
                    )
                  : ""}
              </span>
            </div>

            {preview.warnings.length > 0 ? (
              <div className="flex flex-col gap-1">
                {preview.warnings.map((warning) => (
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

            {preview.sites.length > 0 ? (
              <div className="flex flex-col">
                <div className="flex items-center justify-between pb-1">
                  <span className="text-xs text-muted-foreground">
                    {titleForLocale(
                      locale,
                      `识别到 ${preview.sites.length} 个渠道`,
                      `Recognized ${preview.sites.length} channels`,
                    )}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={toggleAllSites}
                  >
                    {selectedCount === preview.sites.length
                      ? titleForLocale(locale, "全不选", "Deselect all")
                      : titleForLocale(locale, "全选", "Select all")}
                  </Button>
                </div>
                <div className="max-h-80 divide-y overflow-y-auto pr-1">
                  {preview.sites.map((site, index) => {
                    const checkboxId = `foreign-site-${index}`;
                    return (
                      <label
                        key={checkboxId}
                        htmlFor={checkboxId}
                        className="flex cursor-pointer items-center gap-3 py-2.5"
                      >
                        <Checkbox
                          id={checkboxId}
                          checked={selectedIndexes.has(index)}
                          onCheckedChange={() => toggleSite(index)}
                        />
                        <span className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-sm font-medium text-foreground">
                            {site.name}
                            {!site.enabled && (
                              <span className="ml-2 text-xs font-normal text-muted-foreground">
                                {titleForLocale(locale, "已停用", "Disabled")}
                              </span>
                            )}
                          </span>
                          <span className="truncate text-xs text-muted-foreground">
                            {site.base_urls[0] ?? ""}
                            {site.tags.length > 0
                              ? ` · ${site.tags.join(" / ")}`
                              : ""}
                          </span>
                        </span>
                        <span className="hidden shrink-0 items-center gap-2 sm:flex">
                          {site.protocols.map((protocol) => (
                            <span
                              key={protocol}
                              className="flex items-center gap-1 text-xs text-muted-foreground"
                            >
                              <span
                                className={`size-1.5 rounded-full ${PROTOCOL_DOT_CLASS[protocol]}`}
                              />
                              {protocolLabel(protocol, locale)}
                            </span>
                          ))}
                        </span>
                        <span className="w-28 shrink-0 text-right text-xs text-muted-foreground">
                          {titleForLocale(
                            locale,
                            `${site.credential_count} 密钥 · ${site.model_count} 模型`,
                            `${site.credential_count} keys · ${site.model_count} models`,
                          )}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {importResult ? (
              <div className="flex flex-col gap-1.5 rounded-xl bg-muted/40 px-4 py-3">
                <p className="text-sm font-medium text-foreground">
                  {titleForLocale(
                    locale,
                    `已创建 ${importResult.created_count} 个渠道`,
                    `Created ${importResult.created_count} channels`,
                  )}
                  {importResult.skipped_count > 0
                    ? titleForLocale(
                        locale,
                        `，跳过 ${importResult.skipped_count} 个`,
                        `, skipped ${importResult.skipped_count}`,
                      )
                    : null}
                </p>
                {importResult.items
                  .filter(
                    (item) =>
                      item.status !== "created" &&
                      item.status !== "not_committed",
                  )
                  .map((item) => (
                    <p
                      key={item.index}
                      className="text-xs text-muted-foreground"
                    >
                      {item.name}: {importOutcomeReason(item)}
                    </p>
                  ))}
              </div>
            ) : null}

            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-muted-foreground">
                {titleForLocale(
                  locale,
                  `已选 ${selectedCount} / ${preview.sites.length} 个渠道`,
                  `${selectedCount} of ${preview.sites.length} channels selected`,
                )}
              </span>
              <Button
                type="button"
                disabled={
                  selectedCount === 0 ||
                  isImporting ||
                  !preview.payload ||
                  preview.format === "lens"
                }
                onClick={() => void importSelected()}
              >
                <FileInput data-icon="inline-start" />
                {isImporting
                  ? titleForLocale(locale, "导入中...", "Importing...")
                  : titleForLocale(
                      locale,
                      "导入所选渠道",
                      "Import selected channels",
                    )}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
