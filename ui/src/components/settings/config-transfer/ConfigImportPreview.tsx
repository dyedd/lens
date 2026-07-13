import { CircleAlert, FileJson } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemHeader,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/Item";
import type { ConfigBackupDump } from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";
import { ConfigPreviewMeta } from "./ConfigPreviewMeta";
import { formatExportedAt } from "./configTransferUtils";

export type ConfigPreviewSection = {
  key: string;
  label: string;
  count: number;
};

/** Render the selected backup file and parsed preview. */
export function ConfigImportPreview({
  selectedFile,
  preview,
  previewError,
  isPreviewPending,
  previewSections,
  locale,
  timeZone,
}: {
  selectedFile: File | null;
  preview: ConfigBackupDump | null;
  previewError: string;
  isPreviewPending: boolean;
  previewSections: ConfigPreviewSection[];
  locale: Locale;
  timeZone?: string;
}) {
  return (
    <>
      {previewError ? (
        <Alert variant="destructive">
          <CircleAlert />
          <AlertDescription>{previewError}</AlertDescription>
        </Alert>
      ) : null}

      {selectedFile ? (
        <Item variant="muted">
          <ItemMedia variant="icon">
            <FileJson />
          </ItemMedia>
          <ItemContent>
            <ItemTitle className="truncate">{selectedFile.name}</ItemTitle>
            <ItemDescription>
              {Math.max(selectedFile.size / 1024, 0.1).toFixed(1)} KB
            </ItemDescription>
          </ItemContent>
        </Item>
      ) : null}

      {preview ? (
        <Card className="py-0">
          <CardContent className="flex flex-col gap-3 p-4">
            <div className="grid gap-3 md:grid-cols-3">
              <ConfigPreviewMeta
                label={titleForLocale(locale, "版本", "Version")}
                value={"v" + String(preview.version || 1)}
              />
              <ConfigPreviewMeta
                label={titleForLocale(locale, "系统版本", "Lens version")}
                value={preview.lens_version || "n/a"}
              />
              <ConfigPreviewMeta
                label={titleForLocale(locale, "导出时间", "Exported at")}
                value={formatExportedAt(preview.exported_at, locale, timeZone)}
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
          </CardContent>
        </Card>
      ) : selectedFile && isPreviewPending ? (
        <Item variant="muted">
          <ItemMedia variant="icon">
            <FileJson />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>
              {titleForLocale(
                locale,
                "正在解析备份文件...",
                "Parsing backup file...",
              )}
            </ItemTitle>
          </ItemContent>
        </Item>
      ) : null}
    </>
  );
}
