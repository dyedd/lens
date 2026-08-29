import type { QueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { Site } from "@/lib/api/sites";
import type { Locale } from "./channelTypes";

type ChannelFormController = {
  editingSiteId: string | null;
  setEditingSiteId: (value: string | null) => void;
  setIsDialogOpen: (value: boolean) => void;
};

/** Persists channel editor changes and channel status actions. */
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

  return {
    busyId,
    deleteTarget,
    setDeleteTarget,
    removeSite,
    toggleSiteEnabled,
  };
}
