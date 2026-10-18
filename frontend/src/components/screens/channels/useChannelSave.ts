import type { QueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { ModelGroupPlacementResponse } from "@/lib/api/groups";
import type { ChannelModelSyncResponse, Site } from "@/lib/api/sites";
import { toPayload } from "./channelFormConversion";
import type { FormState, Locale } from "./channelTypes";

type ChannelEditor = {
  form: FormState;
  editingSiteId: string | null;
  setEditingSiteId: (value: string | null) => void;
  setIsDialogOpen: (value: boolean) => void;
  applyPreparedForm: (form: FormState) => void;
  validateSiteForm: () => boolean;
  pendingGroupPlacement: { group_id: string; model_names: string[] } | null;
  setPendingGroupPlacement: (
    value: { group_id: string; model_names: string[] } | null,
  ) => void;
};

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
  const createdGroups = result.groups.created_groups.length;
  const pending = result.groups.pending.length;
  if (locale !== "zh-CN") {
    const parts = [
      added && `${added} new models`,
      createdGroups && `${createdGroups} groups created`,
      pending && `${pending} awaiting placement`,
      missing && `${missing} removed upstream`,
      restored && `${restored} back upstream`,
    ].filter(Boolean);
    return parts.length
      ? `Synced: ${parts.join(", ")}`
      : "Models are up to date";
  }
  const parts = [
    added && `新增 ${added} 个模型`,
    createdGroups && `新建 ${createdGroups} 个模型组`,
    pending && `${pending} 个待放置`,
    missing && `${missing} 个已从上游移除`,
    restored && `${restored} 个已恢复`,
  ].filter(Boolean);
  return parts.length ? `已同步：${parts.join("，")}` : "模型已是最新";
}

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
            ? "该渠道已停用，暂时没有可同步的模型"
            : "The channel is disabled, so no models were synchronized",
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
              ? `${failures.length} 个 API Key 获取失败：${failures[0].error}`
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
    }
  }

  /** Joins imported models into the group chosen in the add dialog. */
  async function placePendingModels() {
    const placement = editor.pendingGroupPlacement;
    if (!placement) return;
    editor.setPendingGroupPlacement(null);
    try {
      const result = await apiRequest<ModelGroupPlacementResponse>(
        "/admin/model-group-placements",
        {
          method: "POST",
          body: JSON.stringify({
            model_names: placement.model_names,
            group_id: placement.group_id,
          }),
        },
      );
      const joinedNames = new Set(
        result.joined.map((change) => change.model_name),
      );
      if (joinedNames.size) {
        toast.success(
          locale === "zh-CN"
            ? `已归入模型组：${[...joinedNames].join("、")}`
            : `Joined model group: ${[...joinedNames].join(", ")}`,
        );
      }
      await invalidateChannelData();
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "归入模型组失败" : "Failed to join the group",
        ),
      );
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor.validateSiteForm()) return;
    const editing = Boolean(editor.editingSiteId);
    setIsSaving(true);
    try {
      const site = await persistSite();
      editor.setIsDialogOpen(false);
      editor.setEditingSiteId(null);
      toast.success(
        editing
          ? locale === "zh-CN"
            ? "渠道已保存"
            : "Channel saved"
          : locale === "zh-CN"
            ? "渠道已创建"
            : "Channel created",
      );
      await placePendingModels();
      if (site.enabled) void syncSiteModels(site.id);
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

  return {
    isSaving,
    submit,
  };
}
