"use client";

import { useMemo, useRef, type ChangeEvent } from "react";
import { Download, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AppDialogContent, Dialog } from "@/components/ui/dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import type { SiteBatchImportResult } from "@/lib/api";
import {
  importResultRows,
  importStatusLabel,
  importStatusVariant,
  Locale,
} from "./shared";

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
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const resultRows = useMemo(
    () => (importResult ? importResultRows(importResult, locale) : []),
    [importResult, locale],
  );

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (importing) return;
        onOpenChange(nextOpen);
      }}
    >
      {open ? (
        <AppDialogContent
          className="max-w-3xl"
          title={locale === "zh-CN" ? "批量导入渠道" : "Import channels"}
        >
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
                {locale === "zh-CN" ? "选择 JSON" : "Choose JSON"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={onDownloadTemplate}
                disabled={importing}
              >
                <Download data-icon="inline-start" />
                {locale === "zh-CN" ? "下载模板" : "Template"}
              </Button>
            </div>

            <FieldGroup>
              <Field data-invalid={Boolean(importError)}>
                <FieldLabel htmlFor="channels-batch-import-json">
                  {locale === "zh-CN" ? "JSON 内容" : "JSON"}
                </FieldLabel>
                <Textarea
                  id="channels-batch-import-json"
                  value={importText}
                  onChange={(event) => onTextChange(event.target.value)}
                  className="min-h-[260px] font-mono text-xs"
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
                <div className="grid grid-cols-3 gap-2">
                  <ImportSummaryMetric
                    label={locale === "zh-CN" ? "创建" : "Created"}
                    value={importResult.created_count}
                  />
                  <ImportSummaryMetric
                    label={locale === "zh-CN" ? "跳过" : "Skipped"}
                    value={importResult.skipped_count}
                  />
                  <ImportSummaryMetric
                    label={locale === "zh-CN" ? "错误" : "Errors"}
                    value={importResult.error_count}
                  />
                </div>

                {resultRows.length ? (
                  <div className="max-h-56 overflow-y-auto rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-16">
                            {locale === "zh-CN" ? "序号" : "Index"}
                          </TableHead>
                          <TableHead>
                            {locale === "zh-CN" ? "渠道" : "Channel"}
                          </TableHead>
                          <TableHead className="w-24">
                            {locale === "zh-CN" ? "状态" : "Status"}
                          </TableHead>
                          <TableHead>
                            {locale === "zh-CN" ? "原因" : "Reason"}
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {resultRows.map((row) => (
                          <TableRow key={row.key}>
                            <TableCell>{row.index + 1}</TableCell>
                            <TableCell className="max-w-[180px] truncate">
                              {row.name}
                            </TableCell>
                            <TableCell>
                              <Badge variant={importStatusVariant(row.status)}>
                                {importStatusLabel(row.status, locale)}
                              </Badge>
                            </TableCell>
                            <TableCell
                              className="max-w-[260px] truncate"
                              title={row.reason}
                            >
                              {row.reason || "-"}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={importing}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button type="button" onClick={onImport} disabled={importing}>
                {importing
                  ? locale === "zh-CN"
                    ? "导入中..."
                    : "Importing..."
                  : locale === "zh-CN"
                    ? "导入"
                    : "Import"}
              </Button>
            </div>
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
    <div className="rounded-md border bg-muted/30 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-base font-semibold text-foreground">{value}</div>
    </div>
  );
}
