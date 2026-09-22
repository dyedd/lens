import { FileJson } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemHeader,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/Item";
import { Spinner } from "@/components/ui/Spinner";
import type { ConfigBackupDump } from "@/lib/api/backups";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import { formatExportedAt } from "./backupPreview";

export type ConfigPreviewSection = {
  key: string;
  label: string;
  count: number;
};

/** Render a compact backup preview metadata item. */
function ConfigPreviewMeta({ label, value }: { label: string; value: string }) {
  return (
    <Item variant="muted" size="sm">
      <ItemContent>
        <ItemDescription className="text-[11px] text-muted-foreground">
          {label}
        </ItemDescription>
        <ItemTitle>{value}</ItemTitle>
      </ItemContent>
    </Item>
  );
}

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
        <p className="rounded-md bg-muted/35 px-3 py-2 text-xs leading-5 text-muted-foreground">
          {previewError}
        </p>
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
        <div className="space-y-3 rounded-md bg-muted/35 px-3 py-3">
          <div className="grid gap-3 md:grid-cols-2">
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
                    <Badge
                      variant="secondary"
                      className="h-5 px-1.5 text-[11px] font-normal text-muted-foreground"
                    >
                      {item.count}
                    </Badge>
                  </ItemHeader>
                </ItemContent>
              </Item>
            ))}
          </ItemGroup>
        </div>
      ) : selectedFile && isPreviewPending ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Spinner className="size-3.5" />
          <span>
            {titleForLocale(
              locale,
              "正在解析备份文件...",
              "Parsing backup file...",
            )}
          </span>
        </div>
      ) : null}
    </>
  );
}
