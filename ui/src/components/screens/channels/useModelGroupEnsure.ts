"use client";

import { useState, type FormEvent } from "react";
import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  apiRequest,
  getApiErrorMessage,
  type ModelGroup,
  type ModelGroupEnsureFromSiteResponse,
  type ModelGroupEnsureModelInput,
  type ModelGroupEnsureResultItem,
  type SiteModelGroupSavePayload,
  type SiteModelGroupSaveResponse,
  type SitePayload,
} from "@/lib/api";
import {
  canSubmitModelGroupEnsureItem,
  modelGroupEnsureInputsFromResult,
  modelGroupEnsureSkippedToastMessage,
  modelGroupEnsureResultKey,
} from "./modelGroupEnsure";
import {
  toForm,
  toPayload,
  type FormState,
  type Locale,
} from "./channelShared";

type ChannelEditor = {
  form: FormState;
  editingSiteId: string | null;
  setEditingSiteId: (value: string | null) => void;
  setIsDialogOpen: (value: boolean) => void;
  applyPreparedForm: (form: FormState) => void;
  validateSiteForm: () => boolean;
};

type PendingSave = {
  mode: "create" | "update";
  siteId: string;
  payload: SitePayload;
};

/** Owns the transactional channel save and its ambiguity confirmation dialog. */
export function useModelGroupEnsure({
  locale,
  queryClient,
  editor,
}: {
  locale: Locale;
  queryClient: QueryClient;
  editor: ChannelEditor;
}) {
  const [modelGroupEnsureOpen, setModelGroupEnsureOpenState] = useState(false);
  const [isEnsuringModelGroups, setIsEnsuringModelGroups] = useState(false);
  const [pendingSave, setPendingSave] = useState<PendingSave | null>(null);
  const [result, setResult] = useState<ModelGroupEnsureFromSiteResponse | null>(
    null,
  );
  const [groups, setGroups] = useState<ModelGroup[]>([]);
  const [allowProtocolExtension, setAllowProtocolExtension] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);

  async function requestSave(
    pending: PendingSave,
    options: {
      dryRun: boolean;
      allowProtocolExtension: boolean;
      models: ModelGroupEnsureModelInput[] | null;
    },
  ) {
    const savePayload: SiteModelGroupSavePayload = {
      ...pending.payload,
      site_id: pending.mode === "create" ? pending.siteId || null : null,
      dry_run: options.dryRun,
      allow_protocol_extension: options.allowProtocolExtension,
      models: options.models,
    };
    const path =
      pending.mode === "create"
        ? "/admin/sites/with-model-groups"
        : `/admin/sites/${pending.siteId}/with-model-groups`;
    return apiRequest<SiteModelGroupSaveResponse>(path, {
      method: pending.mode === "create" ? "POST" : "PUT",
      body: JSON.stringify(savePayload),
    });
  }

  function showSkippedToast(nextResult: ModelGroupEnsureFromSiteResponse) {
    const message = modelGroupEnsureSkippedToastMessage(nextResult, locale);
    if (message) toast.warning(message);
  }

  function clearPendingSave() {
    setPendingSave(null);
    setResult(null);
    setGroups([]);
    setAllowProtocolExtension(false);
    setSelectedKeys([]);
  }

  function setModelGroupEnsureOpen(open: boolean) {
    setModelGroupEnsureOpenState(open);
    if (!open) clearPendingSave();
  }

  async function commitSave(
    pending: PendingSave,
    models: ModelGroupEnsureModelInput[] | null,
  ) {
    const committed = await requestSave(pending, {
      dryRun: false,
      allowProtocolExtension,
      models,
    });
    try {
      const updatedGroups = await apiRequest<ModelGroup[]>(
        "/admin/model-groups",
      );
      queryClient.setQueryData(["groups"], updatedGroups);
      queryClient.setQueryData(["model-groups"], updatedGroups);
    } catch {
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
    }
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["sites"] }),
      queryClient.invalidateQueries({ queryKey: ["router-snapshot"] }),
      queryClient.invalidateQueries({ queryKey: ["group-candidates"] }),
    ]);
    editor.applyPreparedForm(toForm(committed.site, locale));
    editor.setIsDialogOpen(false);
    editor.setEditingSiteId(null);
    setModelGroupEnsureOpen(false);
    const changedCount =
      committed.model_groups.created_count +
      committed.model_groups.updated_count;
    toast.success(locale === "zh-CN" ? "渠道已保存" : "Channel saved");
    toast.success(
      locale === "zh-CN"
        ? `已处理 ${changedCount} 项模型组变更`
        : `Processed ${changedCount} model-group changes`,
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor.validateSiteForm()) return;
    setIsEnsuringModelGroups(true);
    setResult(null);
    setGroups([]);
    setAllowProtocolExtension(false);
    setSelectedKeys([]);
    const mode = editor.editingSiteId ? "update" : "create";
    const pending: PendingSave = {
      mode,
      siteId: editor.editingSiteId ?? "",
      payload: toPayload(editor.form),
    };
    try {
      const preview = await requestSave(pending, {
        dryRun: true,
        allowProtocolExtension: false,
        models: null,
      });
      const nextPending = { ...pending, siteId: preview.site.id };
      const nextResult = preview.model_groups;
      if (!nextResult.items.length) {
        await commitSave(nextPending, null);
        return;
      }
      const modelGroups = await queryClient.fetchQuery<ModelGroup[]>({
        queryKey: ["model-groups"],
        queryFn: () => apiRequest<ModelGroup[]>("/admin/model-groups"),
      });
      setPendingSave(nextPending);
      setGroups(modelGroups);
      setResult(nextResult);
      setSelectedKeys(
        nextResult.items
          .filter(canSubmitModelGroupEnsureItem)
          .map(modelGroupEnsureResultKey),
      );
      showSkippedToast(nextResult);
      setModelGroupEnsureOpen(true);
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "保存渠道失败" : "Failed to save channel",
        ),
      );
    } finally {
      setIsEnsuringModelGroups(false);
    }
  }

  async function previewWithModels(
    models: ModelGroupEnsureModelInput[],
    allowed: boolean,
  ) {
    if (!pendingSave) return;
    setIsEnsuringModelGroups(true);
    try {
      const preview = await requestSave(pendingSave, {
        dryRun: true,
        allowProtocolExtension: allowed,
        models,
      });
      setResult(preview.model_groups);
      showSkippedToast(preview.model_groups);
      return preview.model_groups;
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN"
            ? "更新模型组预览失败"
            : "Failed to update model group preview",
        ),
      );
      return null;
    } finally {
      setIsEnsuringModelGroups(false);
    }
  }

  async function updateTarget(item: ModelGroupEnsureResultItem, group: string) {
    if (!result) return;
    const changedKey = modelGroupEnsureResultKey(item);
    const wasSelected = selectedKeys.includes(changedKey);
    const nextResult = await previewWithModels(
      modelGroupEnsureInputsFromResult(
        result.items,
        new Map([[changedKey, group]]),
      ),
      allowProtocolExtension,
    );
    if (!nextResult) return;
    setSelectedKeys((current) => {
      const executable = new Set(
        nextResult.items
          .filter(canSubmitModelGroupEnsureItem)
          .map(modelGroupEnsureResultKey),
      );
      const next = current.filter((key) => executable.has(key));
      const changed = nextResult.items.find(
        (row) => modelGroupEnsureResultKey(row) === changedKey,
      );
      if (
        changed &&
        canSubmitModelGroupEnsureItem(changed) &&
        (wasSelected || !canSubmitModelGroupEnsureItem(item)) &&
        !next.includes(changedKey)
      ) {
        next.push(changedKey);
      }
      return next;
    });
  }

  async function updateProtocolExtension(allowed: boolean) {
    if (!result) return;
    setAllowProtocolExtension(allowed);
    const nextResult = await previewWithModels(
      modelGroupEnsureInputsFromResult(result.items),
      allowed,
    );
    if (!nextResult) {
      setAllowProtocolExtension(!allowed);
      return;
    }
    setSelectedKeys((current) => {
      const executable = new Set(
        nextResult.items
          .filter(canSubmitModelGroupEnsureItem)
          .map(modelGroupEnsureResultKey),
      );
      return allowed
        ? Array.from(executable)
        : current.filter((key) => executable.has(key));
    });
  }

  function toggleItem(item: ModelGroupEnsureResultItem) {
    if (!canSubmitModelGroupEnsureItem(item)) return;
    const key = modelGroupEnsureResultKey(item);
    setSelectedKeys((current) =>
      current.includes(key)
        ? current.filter((itemKey) => itemKey !== key)
        : [...current, key],
    );
  }

  async function confirm(groupOverrides: Record<string, string> = {}) {
    if (!result || !pendingSave) return;
    const selected = new Set(selectedKeys);
    const overrides = new Map(
      Object.entries(groupOverrides)
        .map(([key, value]) => [key, value.trim()] as const)
        .filter(([, value]) => value),
    );
    const models = modelGroupEnsureInputsFromResult(
      result.items.filter(
        (item) =>
          canSubmitModelGroupEnsureItem(item) &&
          selected.has(modelGroupEnsureResultKey(item)),
      ),
      overrides,
    );
    setIsEnsuringModelGroups(true);
    try {
      await commitSave(pendingSave, models);
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN"
            ? "保存渠道或模型组失败"
            : "Failed to save channel or model groups",
        ),
      );
    } finally {
      setIsEnsuringModelGroups(false);
    }
  }

  return {
    modelGroupEnsureOpen,
    setModelGroupEnsureOpen,
    isEnsuringModelGroups,
    result,
    groups,
    allowProtocolExtension,
    selectedKeys,
    submit,
    updateTarget,
    updateProtocolExtension,
    toggleItem,
    confirm,
  };
}
