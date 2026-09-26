import type { QueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type {
  Site,
  SiteBatchImportPayload,
  SiteBatchImportResult,
} from "@/lib/api/sites";
import {
  batchImportTemplateText,
  parseBatchImportPayload,
} from "./channelBatchImport";
import type { Locale } from "./channelTypes";

type ChannelFormController = {
  editingSiteId: string | null;
  setEditingSiteId: (value: string | null) => void;
  setIsDialogOpen: (value: boolean) => void;
};

export function useChannelPersistence({
  locale,
  queryClient,
  invalidateChannelData,
  editor,
}: {
  locale: Locale;
  queryClient: QueryClient;
  invalidateChannelData: () => Promise<void>;
  editor: ChannelFormController;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Site | null>(null);

  async function removeSite(site: Site) {
    setBusyId(site.id);
    try {
      await apiRequest<void>(`/admin/sites/${site.id}`, { method: "DELETE" });
      queryClient.setQueryData<Site[]>(["sites"], (current) =>
        (current ?? []).filter((item) => item.id !== site.id),
      );
      setDeleteTarget(null);
      if (editor.editingSiteId === site.id) {
        editor.setIsDialogOpen(false);
        editor.setEditingSiteId(null);
      }
      toast.success(locale === "zh-CN" ? "渠道已删除" : "Channel deleted");
      await invalidateChannelData();
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "删除渠道失败" : "Failed to delete channel",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function toggleSiteEnabled(site: Site, enabled: boolean) {
    setBusyId(site.id);
    try {
      const updatedSite = await apiRequest<Site>(
        `/admin/sites/${site.id}/enabled`,
        {
          method: "PUT",
          body: JSON.stringify({ enabled }),
        },
      );
      queryClient.setQueryData<Site[]>(["sites"], (current) =>
        (current ?? []).map((item) =>
          item.id === updatedSite.id ? updatedSite : item,
        ),
      );
      toast.success(
        enabled
          ? locale === "zh-CN"
            ? "渠道已启用"
            : "Channel enabled"
          : locale === "zh-CN"
            ? "渠道已停用"
            : "Channel disabled",
      );
      await invalidateChannelData();
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN"
            ? "更新渠道状态失败"
            : "Failed to update channel status",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function applyEnabled(sites: Site[], enabled: boolean) {
    const targets = sites.filter((site) => site.enabled !== enabled);
    if (!targets.length) return;
    setBusyId("bulk");
    try {
      for (const site of targets) {
        const updatedSite = await apiRequest<Site>(
          `/admin/sites/${site.id}/enabled`,
          {
            method: "PUT",
            body: JSON.stringify({ enabled }),
          },
        );
        queryClient.setQueryData<Site[]>(["sites"], (current) =>
          (current ?? []).map((item) =>
            item.id === updatedSite.id ? updatedSite : item,
          ),
        );
      }
      toast.success(
        enabled
          ? locale === "zh-CN"
            ? `已启用 ${targets.length} 个渠道`
            : `Enabled ${targets.length} channels`
          : locale === "zh-CN"
            ? `已停用 ${targets.length} 个渠道`
            : `Disabled ${targets.length} channels`,
      );
      await invalidateChannelData();
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN"
            ? "批量更新渠道状态失败"
            : "Failed to update channel status",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function removeSites(sites: Site[]) {
    if (!sites.length) return;
    setBusyId("bulk");
    try {
      const removedIds = new Set<string>();
      for (const site of sites) {
        await apiRequest<void>(`/admin/sites/${site.id}`, { method: "DELETE" });
        removedIds.add(site.id);
      }
      queryClient.setQueryData<Site[]>(["sites"], (current) =>
        (current ?? []).filter((item) => !removedIds.has(item.id)),
      );
      setDeleteTarget(null);
      toast.success(
        locale === "zh-CN"
          ? `已删除 ${sites.length} 个渠道`
          : `Deleted ${sites.length} channels`,
      );
      await invalidateChannelData();
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "批量删除渠道失败" : "Failed to delete channels",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  return {
    busyId,
    deleteTarget,
    setDeleteTarget,
    removeSite,
    removeSites,
    toggleSiteEnabled,
    applyEnabled,
  };
}

/** Owns the batch channel import workflow. */
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
      const createdSites = result.items.flatMap((item) =>
        item.status === "created" ? [item.site] : [],
      );
      if (createdSites.length) {
        queryClient.setQueryData<Site[]>(["sites"], (current) => {
          const rows = current ?? [];
          const ids = new Set(rows.map((site) => site.id));
          return [...createdSites.filter((site) => !ids.has(site.id)), ...rows];
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
  };
}
