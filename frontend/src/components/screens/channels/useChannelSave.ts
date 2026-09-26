import type { QueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { ChannelModelSyncResponse, Site } from "@/lib/api/sites";
import { toForm, toPayload } from "./channelFormConversion";
import type { FormState, Locale } from "./channelTypes";

type ChannelEditor = {
  form: FormState;
  editingSiteId: string | null;
  hasUnsavedChanges: boolean;
  setEditingSiteId: (value: string | null) => void;
  setIsDialogOpen: (value: boolean) => void;
  applyPreparedForm: (form: FormState) => void;
  validateSiteForm: () => boolean;
};

/** Identifies the inputs whose change makes the upstream catalog worth re-reading. */
function modelSyncSourceKey(site: Site) {
  return JSON.stringify([
    site.model_sync_enabled,
    site.model_sync_include,
    site.model_sync_exclude,
    site.base_urls.map((item) => item.url),
    site.credentials.map((item) => item.api_key),
  ]);
}

function countSyncedNames(
  result: ChannelModelSyncResponse,
  field: "added" | "missing" | "restored",
) {
  return new Set(result.items.flatMap((item) => item[field])).size;
}

function formatSyncSummary(
  result: ChannelModelSyncResponse,
  locale: Locale,
): string {
  const added = countSyncedNames(result, "added");
  const missing = countSyncedNames(result, "missing");
  const restored = countSyncedNames(result, "restored");
  if (locale !== "zh-CN") {
    const parts = [
      added && `${added} new models ready to call`,
      missing && `${missing} missing upstream to review`,
      restored && `${restored} back upstream`,
    ].filter(Boolean);
    return parts.length
      ? `Synced: ${parts.join(", ")}`
      : "Models are up to date";
  }
  const parts = [
    added && `新增 ${added} 个模型，可直接调用`,
    missing && `${missing} 个上游缺失待确认`,
    restored && `${restored} 个已恢复`,
  ].filter(Boolean);
  return parts.length ? `已同步：${parts.join("，")}` : "模型已是最新";
}

/** Saves channels and runs the upstream model sync the save calls for. */
export function useChannelSave({
  locale,
  queryClient,
  invalidateChannelData,
  editor,
}: {
  locale: Locale;
  queryClient: QueryClient;
  invalidateChannelData: () => Promise<void>;
  editor: ChannelEditor;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [syncingSiteId, setSyncingSiteId] = useState<string | null>(null);

  function cachedSite(siteId: string | null) {
    return siteId
      ? queryClient
          .getQueryData<Site[]>(["sites"])
          ?.find((site) => site.id === siteId)
      : undefined;
  }

  async function persistSite() {
    const body = JSON.stringify(toPayload(editor.form));
    const site = editor.editingSiteId
      ? await apiRequest<Site>(`/admin/sites/${editor.editingSiteId}`, {
          method: "PUT",
          body,
        })
      : await apiRequest<Site>("/admin/sites", { method: "POST", body });
    queryClient.setQueryData<Site[]>(["sites"], (current) => [
      site,
      ...(current ?? []).filter((item) => item.id !== site.id),
    ]);
    return site;
  }

  async function syncSiteModels(siteId: string) {
    setSyncingSiteId(siteId);
    try {
      const result = await apiRequest<ChannelModelSyncResponse>(
        "/admin/channel-model-sync",
        { method: "POST", body: JSON.stringify({ site_ids: [siteId] }) },
      );
      await invalidateChannelData();
      const failures = result.items.filter((item) => item.status === "failed");
      if (!result.items.length) {
        toast.info(
          locale === "zh-CN"
            ? "该渠道未开启自动同步或已停用"
            : "Auto-sync is off or the channel is disabled",
        );
      } else if (failures.length === result.items.length) {
        toast.error(
          locale === "zh-CN" ? "同步上游模型失败" : "Failed to sync models",
          { description: failures[0].error },
        );
      } else if (failures.length) {
        toast.warning(formatSyncSummary(result, locale), {
          description:
            locale === "zh-CN"
              ? `${failures.length} 个密钥获取失败：${failures[0].error}`
              : `${failures.length} keys failed: ${failures[0].error}`,
        });
      } else {
        toast.success(formatSyncSummary(result, locale));
      }
      return result;
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "同步上游模型失败" : "Failed to sync models",
        ),
      );
      return null;
    } finally {
      setSyncingSiteId(null);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor.validateSiteForm()) return;
    const previousSite = cachedSite(editor.editingSiteId);
    setIsSaving(true);
    try {
      const site = await persistSite();
      editor.setIsDialogOpen(false);
      editor.setEditingSiteId(null);
      toast.success(
        previousSite
          ? locale === "zh-CN"
            ? "渠道已保存"
            : "Channel saved"
          : locale === "zh-CN"
            ? "渠道已创建"
            : "Channel created",
      );
      const shouldSync =
        site.enabled &&
        site.model_sync_enabled &&
        (!previousSite ||
          modelSyncSourceKey(previousSite) !== modelSyncSourceKey(site));
      if (shouldSync) void syncSiteModels(site.id);
      else void invalidateChannelData();
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "保存渠道失败" : "Failed to save channel",
        ),
      );
    } finally {
      setIsSaving(false);
    }
  }

  /** Saves pending edits, syncs now, and reloads the editor in place. */
  async function syncEditorModels() {
    if (!editor.validateSiteForm()) return;
    setIsSaving(true);
    try {
      const site =
        editor.hasUnsavedChanges || !editor.editingSiteId
          ? await persistSite()
          : cachedSite(editor.editingSiteId);
      if (!site) return;
      editor.setEditingSiteId(site.id);
      await syncSiteModels(site.id);
      editor.applyPreparedForm(toForm(cachedSite(site.id) ?? site));
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "保存渠道失败" : "Failed to save channel",
        ),
      );
    } finally {
      setIsSaving(false);
    }
  }

  return {
    isSaving,
    syncingSiteId,
    submit,
    syncSiteModels,
    syncEditorModels,
  };
}
