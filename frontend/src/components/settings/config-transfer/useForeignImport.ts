import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { getApiErrorMessage } from "@/lib/api/client";
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
  const previewController = useRef<AbortController | null>(null);

  useEffect(() => () => previewController.current?.abort(), []);

  async function loadFile(nextFile: File | null) {
    if (isImporting) return;
    previewController.current?.abort();
    const controller = new AbortController();
    previewController.current = controller;
    setFile(nextFile);
    setPreview(null);
    setSelectedIndexes(new Set());
    setImportResult(null);
    if (!nextFile) {
      setIsPreviewing(false);
      return;
    }

    setIsPreviewing(true);
    try {
      const nextPreview = await previewForeignSiteImport(
        nextFile,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setPreview(nextPreview);
      setSelectedIndexes(new Set(nextPreview.sites.map((_, index) => index)));
    } catch (error) {
      if (controller.signal.aborted) return;
      setFile(null);
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(locale, "预览失败", "Failed to preview backup"),
        ),
      );
    } finally {
      if (previewController.current === controller) setIsPreviewing(false);
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
    if (!preview?.payload || isImporting) {
      return;
    }

    setIsImporting(true);
    try {
      const payloadSites = preview.payload.sites.filter((_, index) =>
        selectedIndexes.has(index),
      );
      const result = await importForeignSites({ sites: payloadSites });
      setImportResult(result);
      if (result.error_count > 0) {
        toast.error(
          titleForLocale(
            locale,
            "校验失败，整批未导入",
            "Validation failed; no channels were imported",
          ),
        );
        return;
      }
      setSelectedIndexes(new Set());
      await queryClient.invalidateQueries();
      if (result.created_count > 0) {
        toast.success(
          titleForLocale(
            locale,
            `已导入 ${result.created_count} 个渠道`,
            `Imported ${result.created_count} channels`,
          ),
        );
      } else {
        toast(
          titleForLocale(
            locale,
            "所有渠道均已跳过",
            "All channels were skipped",
          ),
        );
      }
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(locale, "导入失败", "Failed to import channels"),
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
