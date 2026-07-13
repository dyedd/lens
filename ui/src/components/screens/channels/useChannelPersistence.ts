"use client";

import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import type { QueryClient } from "@tanstack/react-query";
import { apiRequest, getApiErrorMessage, type Site } from "@/lib/api";
import {
  toForm,
  toPayload,
  type FormState,
  type Locale,
} from "./channelShared";

type ChannelFormController = {
  editingSiteId: string | null;
  setEditingSiteId: (value: string | null) => void;
  setIsDialogOpen: (value: boolean) => void;
  form: FormState;
  applyPreparedForm: (form: FormState) => void;
  validateSiteForm: () => boolean;
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

  async function saveCurrentSite({ keepEditing = false } = {}) {
    const wasEditing = Boolean(editor.editingSiteId);
    const savedSite = await apiRequest<Site>(
      editor.editingSiteId
        ? `/admin/sites/${editor.editingSiteId}`
        : "/admin/sites",
      {
        method: editor.editingSiteId ? "PUT" : "POST",
        body: JSON.stringify(toPayload(editor.form)),
      },
    );
    queryClient.setQueryData<Site[]>(["sites"], (current) => {
      const rows = current ?? [];
      return rows.some((site) => site.id === savedSite.id)
        ? rows.map((site) => (site.id === savedSite.id ? savedSite : site))
        : [savedSite, ...rows];
    });
    editor.applyPreparedForm(toForm(savedSite, locale));
    if (keepEditing) editor.setEditingSiteId(savedSite.id);
    await invalidateChannelData();
    return { savedSite, wasEditing };
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor.validateSiteForm()) return;
    try {
      const { wasEditing } = await saveCurrentSite();
      editor.setIsDialogOpen(false);
      editor.setEditingSiteId(null);
      toast.success(
        wasEditing
          ? locale === "zh-CN"
            ? "渠道已更新"
            : "Channel updated"
          : locale === "zh-CN"
            ? "渠道已创建"
            : "Channel created",
      );
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "保存渠道失败" : "Failed to save channel",
        ),
      );
    }
  }

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
      const updatedSite = await apiRequest<Site>(`/admin/sites/${site.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: site.name,
          base_urls: site.base_urls.map((item) => ({
            id: item.id,
            url: item.url,
            name: item.name,
            enabled: item.enabled,
            supported_protocols: item.supported_protocols ?? [],
          })),
          credentials: site.credentials.map((item) => ({
            id: item.id,
            name: item.name,
            api_key: item.api_key,
            enabled: item.enabled,
          })),
          protocols: site.protocols.map((config) => ({
            id: config.id,
            name: config.name,
            protocols: config.protocols,
            enabled,
            headers: config.headers,
            proxy_mode: config.proxy_mode,
            channel_proxy: config.channel_proxy,
            param_override: config.param_override,
            match_regex: config.match_regex,
            base_url_id: config.base_url_id,
            credential_id: config.credential_id,
            models: config.models.map((model) => ({
              id: model.id,
              protocol: model.protocol,
              credential_id: model.credential_id,
              model_name: model.model_name,
              enabled: model.enabled,
            })),
          })),
        }),
      });
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
    saveCurrentSite,
    submit,
    removeSite,
    toggleSiteEnabled,
  };
}
