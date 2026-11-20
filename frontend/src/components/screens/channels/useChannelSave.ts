import type { QueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { Site } from "@/lib/api/sites";
import { toPayload } from "./channelFormConversion";
import type { FormState, Locale } from "./channelTypes";

type ChannelEditor = {
  form: FormState;
  editingSiteId: string | null;
  setEditingSiteId: (value: string | null) => void;
  setIsDialogOpen: (value: boolean) => void;
  validateSiteForm: () => boolean;
};

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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor.validateSiteForm()) return;
    const editing = Boolean(editor.editingSiteId);
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
      void invalidateChannelData();
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
