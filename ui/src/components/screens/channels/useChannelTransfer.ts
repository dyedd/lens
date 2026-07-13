"use client";

import { useState, type ChangeEvent } from "react";
import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  apiRequest,
  getApiErrorMessage,
  type ChannelModelSyncResponse,
  type Site,
  type SiteBatchImportPayload,
  type SiteBatchImportResult,
} from "@/lib/api";
import {
  batchImportTemplateText,
  parseBatchImportPayload,
  type Locale,
} from "./channelShared";

/** Owns batch import and channel-model synchronization workflows. */
export function useChannelTransfer({
  locale,
  queryClient,
  invalidateChannelData,
}: {
  locale: Locale;
  queryClient: QueryClient;
  invalidateChannelData: () => Promise<void>;
}) {
  const [batchImportOpen, setBatchImportOpen] = useState(false);
  const [batchImportText, setBatchImportText] = useState("");
  const [batchImportError, setBatchImportError] = useState("");
  const [batchImportResult, setBatchImportResult] =
    useState<SiteBatchImportResult | null>(null);
  const [batchImporting, setBatchImporting] = useState(false);
  const [channelSyncOpen, setChannelSyncOpen] = useState(false);
  const [channelSyncResult, setChannelSyncResult] =
    useState<ChannelModelSyncResponse | null>(null);
  const [channelSyncing, setChannelSyncing] = useState(false);

  function openBatchImport() {
    setBatchImportText("");
    setBatchImportError("");
    setBatchImportResult(null);
    setBatchImportOpen(true);
  }
  function updateBatchImportText(value: string) {
    setBatchImportText(value);
    setBatchImportError("");
    setBatchImportResult(null);
  }
  async function handleBatchImportFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      updateBatchImportText(await file.text());
    } catch (error) {
      setBatchImportError(
        error instanceof Error
          ? error.message
          : locale === "zh-CN"
            ? "读取文件失败"
            : "Failed to read file",
      );
      setBatchImportResult(null);
    }
  }
  function downloadBatchImportTemplate() {
    const url = URL.createObjectURL(
      new Blob([batchImportTemplateText()], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "lens-channels-import-template.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }
  async function importBatchSites() {
    let payload: SiteBatchImportPayload;
    try {
      payload = parseBatchImportPayload(batchImportText, locale);
    } catch (error) {
      setBatchImportError(
        error instanceof Error
          ? error.message
          : locale === "zh-CN"
            ? "JSON 格式无效"
            : "Invalid JSON format",
      );
      setBatchImportResult(null);
      return;
    }
    setBatchImporting(true);
    setBatchImportError("");
    try {
      const result = await apiRequest<SiteBatchImportResult>(
        "/admin/sites/import",
        { method: "POST", body: JSON.stringify(payload) },
      );
      setBatchImportResult(result);
      if (result.error_count) {
        toast.error(
          locale === "zh-CN"
            ? "导入校验失败"
            : "Channel import validation failed",
        );
        return;
      }
      if (result.created.length) {
        queryClient.setQueryData<Site[]>(["sites"], (current) => {
          const rows = current ?? [];
          const ids = new Set(rows.map((site) => site.id));
          return [
            ...result.created.filter((site) => !ids.has(site.id)),
            ...rows,
          ];
        });
        await invalidateChannelData();
        toast.success(
          locale === "zh-CN"
            ? `已导入 ${result.created_count} 个渠道`
            : `Imported ${result.created_count} channels`,
        );
        if (!result.skipped_count) setBatchImportOpen(false);
        return;
      }
      toast.info(
        locale === "zh-CN"
          ? "没有新的渠道被导入"
          : "No new channels were imported",
      );
    } catch (error) {
      setBatchImportError(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "导入渠道失败" : "Failed to import channels",
        ),
      );
      setBatchImportResult(null);
    } finally {
      setBatchImporting(false);
    }
  }
  async function openChannelModelSync() {
    setChannelSyncResult(null);
    setChannelSyncOpen(true);
    setChannelSyncing(true);
    try {
      setChannelSyncResult(
        await apiRequest<ChannelModelSyncResponse>(
          "/admin/channel-model-sync",
          { method: "POST", body: JSON.stringify({ dry_run: true }) },
        ),
      );
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "生成同步预览失败" : "Failed to preview sync",
        ),
      );
      setChannelSyncOpen(false);
    } finally {
      setChannelSyncing(false);
    }
  }
  async function confirmChannelModelSync() {
    setChannelSyncing(true);
    try {
      const result = await apiRequest<ChannelModelSyncResponse>(
        "/admin/channel-model-sync",
        { method: "POST", body: JSON.stringify({ dry_run: false }) },
      );
      await invalidateChannelData();
      const added = result.items.reduce(
        (sum, item) => sum + item.added.length,
        0,
      );
      const removed = result.items.reduce(
        (sum, item) => sum + item.removed.length,
        0,
      );
      toast.success(
        locale === "zh-CN"
          ? `已同步 ${result.synced_channel_count} 个渠道，新增 ${added} 个，移除 ${removed} 个`
          : `Synced ${result.synced_channel_count} channels, +${added} / -${removed}`,
      );
      setChannelSyncOpen(false);
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "同步失败" : "Sync failed",
        ),
      );
    } finally {
      setChannelSyncing(false);
    }
  }
  return {
    batchImportOpen,
    setBatchImportOpen,
    batchImportText,
    batchImportError,
    batchImportResult,
    batchImporting,
    openBatchImport,
    updateBatchImportText,
    handleBatchImportFile,
    downloadBatchImportTemplate,
    importBatchSites,
    channelSyncOpen,
    setChannelSyncOpen,
    channelSyncResult,
    channelSyncing,
    openChannelModelSync,
    confirmChannelModelSync,
  };
}
