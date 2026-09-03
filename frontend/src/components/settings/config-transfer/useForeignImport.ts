import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import {
  type ForeignSiteImportPreview,
  importForeignSites,
  previewForeignSiteImport,
} from "@/lib/api/foreignImports";
import type { SiteBatchImportResult } from "@/lib/api/sites";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

/** Orchestrates the foreign backup file detection, selection, and import flow. */
export function useForeignImport(locale: Locale) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ForeignSiteImportPreview | null>(null);
  const [selectedIndexes, setSelectedIndexes] = useState<ReadonlySet<number>>(
    new Set(),
  );
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] =
    useState<SiteBatchImportResult | null>(null);

  async function loadFile(nextFile: File | null) {
    setFile(nextFile);
    setPreview(null);
    setSelectedIndexes(new Set());
    setImportResult(null);
    if (!nextFile) {
      return;
    }

    setIsPreviewing(true);
    try {
      const nextPreview = await previewForeignSiteImport(nextFile);
      setPreview(nextPreview);
      setSelectedIndexes(new Set(nextPreview.sites.map((_, index) => index)));
    } catch {
      setFile(null);
      toast.error(
        titleForLocale(
          locale,
          "无法识别该备份文件的格式",
          "Could not recognize this backup file",
        ),
      );
    } finally {
      setIsPreviewing(false);
    }
  }

  function toggleSite(index: number) {
    setSelectedIndexes((current) => {
      const next = new Set(current);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }

  function toggleAllSites() {
    if (!preview) {
      return;
    }
    setSelectedIndexes((current) =>
      current.size === preview.sites.length
        ? new Set()
        : new Set(preview.sites.map((_, index) => index)),
    );
  }

  async function importSelected() {
    if (!preview?.payload) {
      return;
    }

    setIsImporting(true);
    try {
      const payloadSites = preview.payload.sites.filter((_, index) =>
        selectedIndexes.has(index),
      );
      const result = await importForeignSites({ sites: payloadSites });
      setImportResult(result);
      setSelectedIndexes(new Set());
      await queryClient.invalidateQueries();
      toast.success(
        titleForLocale(
          locale,
          `已导入 ${result.created_count} 个渠道`,
          `Imported ${result.created_count} channels`,
        ),
      );
    } catch {
      toast.error(
        titleForLocale(
          locale,
          "导入失败，请重试",
          "Import failed, please retry",
        ),
      );
    } finally {
      setIsImporting(false);
    }
  }

  return {
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
  };
}
