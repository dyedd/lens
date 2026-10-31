import type { QueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
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
};

function countSyncedNames(
  result: ChannelModelSyncResponse,
  field: "added" | "missing",
) {
  return new Set(result.items.flatMap((item) => item[field])).size;
}

function formatSyncSummary(
  result: ChannelModelSyncResponse,
  locale: Locale,
): string {
  const added = countSyncedNames(result, "added");
  const removed = countSyncedNames(result, "missing");
  const createdGroups = result.groups.created_groups.length;
  const pending = result.groups.pending.length;
  if (locale !== "zh-CN") {
    const parts = [
      added && `${added} new models`,
      createdGroups && `${createdGroups} groups created`,
      pending && `${pending} awaiting placement`,
      removed && `${removed} removed`,
    ].filter(Boolean);
    return parts.length
      ? `Synced: ${parts.join(", ")}`
      : "Models are up to date";
  }
  const parts = [
    added && `新增 ${added} 个模型`,
    createdGroups && `新建 ${createdGroups} 个模型组`,
    pending && `${pending} 个待放置`,
    removed && `移除 ${removed} 个模型`,
  ].filter(Boolean);
  return parts.length ? `已同步：${parts.join("，")}` : "模型已是最新";
}

export function useChannelSave({
  locale,
  queryClient,
  invalidateChannelData,
  editor,
  onCreated,
}: {
  locale: Locale;
  queryClient: QueryClient;
  invalidateChannelData: () => Promise<void>;
  editor: ChannelEditor;
  onCreated?: (site: Site) => void;
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

  function changedCredentialIds() {
    const nextCredentials = toPayload(editor.form).credentials;
    if (!editor.editingSiteId) {
      return nextCredentials
        .filter((credential) => (credential.model_pattern ?? "").trim())
        .map((credential) => credential.id)
        .filter((id): id is string => Boolean(id));
    }
    const previousSite = queryClient
      .getQueryData<Site[]>(["sites"])
      ?.find((item) => item.id === editor.editingSiteId);
    if (!previousSite) return [];
    const previousPatterns = new Map(
      previousSite.credentials.map((credential) => [
        credential.id,
        (credential.model_pattern ?? "").trim(),
      ]),
    );
    return nextCredentials
      .filter(
        (credential) =>
          credential.id != null &&
          (credential.model_pattern ?? "").trim() !==
            previousPatterns.get(credential.id),
      )
      .map((credential) => credential.id)
      .filter((id): id is string => Boolean(id));
  }

  async function syncSiteModels(siteId: string, credentialIds?: string[]) {
    try {
      const result = await apiRequest<ChannelModelSyncResponse>(
        "/admin/channel-model-sync",
        {
          method: "POST",
          body: JSON.stringify({
            site_ids: [siteId],
            ...(credentialIds ? { credential_ids: credentialIds } : {}),
          }),
        },
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor.validateSiteForm()) return;
    const editing = Boolean(editor.editingSiteId);
    const credentialIds = changedCredentialIds();
    setIsSaving(true);
    try {
      const site = await persistSite();
      if (!editing && onCreated) {
        onCreated(site);
      } else {
        editor.setIsDialogOpen(false);
        editor.setEditingSiteId(null);
      }
      toast.success(
        editing
          ? locale === "zh-CN"
            ? "渠道已保存"
            : "Channel saved"
          : locale === "zh-CN"
            ? "渠道已创建"
            : "Channel created",
      );
      if (site.enabled && (credentialIds?.length ?? 0) > 0) {
        void syncSiteModels(site.id, credentialIds);
      } else {
        void invalidateChannelData();
      }
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
