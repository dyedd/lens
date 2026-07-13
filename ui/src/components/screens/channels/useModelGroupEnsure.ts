"use client";

import { useState } from "react";
import type { QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  apiRequest,
  getApiErrorMessage,
  type ModelGroup,
  type ModelGroupEnsureFromSitePayload,
  type ModelGroupEnsureFromSiteResponse,
  type ModelGroupEnsureModelInput,
  type ModelGroupEnsureResultItem,
  type Site,
} from "@/lib/api";
import {
  canSubmitModelGroupEnsureItem,
  executionModelGroups,
  modelGroupEnsureInputsFromResult,
  modelGroupEnsureResultKey,
} from "./modelGroupEnsure";
import {
  buildModelGroupEnsureInputs,
  showModelGroupEnsureSkippedToast,
} from "./modelGroupEnsurePayload";
import type { Locale } from "./channelShared";

type SaveSite = (options: { keepEditing: true }) => Promise<{
  savedSite: Site;
  wasEditing: boolean;
}>;

/** Owns the model-group preview and confirmation workflow. */
export function useModelGroupEnsure({
  locale,
  queryClient,
  validateSiteForm,
  saveCurrentSite,
  invalidateChannelData,
}: {
  locale: Locale;
  queryClient: QueryClient;
  validateSiteForm: () => boolean;
  saveCurrentSite: SaveSite;
  invalidateChannelData: () => Promise<void>;
}) {
  const [modelGroupEnsureOpen, setModelGroupEnsureOpen] = useState(false);
  const [isEnsuringModelGroups, setIsEnsuringModelGroups] = useState(false);
  const [siteId, setSiteId] = useState("");
  const [result, setResult] = useState<ModelGroupEnsureFromSiteResponse | null>(
    null,
  );
  const [groups, setGroups] = useState<ModelGroup[]>([]);
  const [allowProtocolExtension, setAllowProtocolExtension] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);

  async function requestPreview(
    models: ModelGroupEnsureModelInput[],
    allowed: boolean,
  ) {
    return apiRequest<ModelGroupEnsureFromSiteResponse>(
      "/admin/model-groups/ensure-from-site",
      {
        method: "POST",
        body: JSON.stringify({
          site_id: siteId,
          dry_run: true,
          allow_protocol_extension: allowed,
          models,
        } satisfies ModelGroupEnsureFromSitePayload),
      },
    );
  }
  async function openModelGroupEnsureDialog() {
    if (!validateSiteForm()) return;
    setIsEnsuringModelGroups(true);
    setResult(null);
    setGroups([]);
    setAllowProtocolExtension(false);
    setSelectedKeys([]);
    try {
      const { savedSite } = await saveCurrentSite({ keepEditing: true });
      const modelGroups = await queryClient.fetchQuery<ModelGroup[]>({
        queryKey: ["model-groups"],
        queryFn: () => apiRequest<ModelGroup[]>("/admin/model-groups"),
      });
      const models = buildModelGroupEnsureInputs(
        savedSite,
        executionModelGroups(modelGroups),
      );
      if (!models.length) {
        toast.info(
          locale === "zh-CN"
            ? "没有可加入模型组的启用模型"
            : "No enabled models can be added to groups",
        );
        return;
      }
      const nextResult = await apiRequest<ModelGroupEnsureFromSiteResponse>(
        "/admin/model-groups/ensure-from-site",
        {
          method: "POST",
          body: JSON.stringify({
            site_id: savedSite.id,
            dry_run: true,
            allow_protocol_extension: false,
            models,
          } satisfies ModelGroupEnsureFromSitePayload),
        },
      );
      setSiteId(savedSite.id);
      setGroups(modelGroups);
      setResult(nextResult);
      setSelectedKeys(
        nextResult.items
          .filter(canSubmitModelGroupEnsureItem)
          .map(modelGroupEnsureResultKey),
      );
      showModelGroupEnsureSkippedToast(nextResult, locale);
      setModelGroupEnsureOpen(true);
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN"
            ? "生成模型组预览失败"
            : "Failed to preview model groups",
        ),
      );
    } finally {
      setIsEnsuringModelGroups(false);
    }
  }
  async function updateTarget(item: ModelGroupEnsureResultItem, group: string) {
    if (!result || !siteId) return;
    const changedKey = modelGroupEnsureResultKey(item);
    const wasSelected = selectedKeys.includes(changedKey);
    setIsEnsuringModelGroups(true);
    try {
      const nextResult = await requestPreview(
        modelGroupEnsureInputsFromResult(
          result.items,
          new Map([[changedKey, group]]),
        ),
        allowProtocolExtension,
      );
      setResult(nextResult);
      showModelGroupEnsureSkippedToast(nextResult, locale);
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
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN"
            ? "更新模型组预览失败"
            : "Failed to update model group preview",
        ),
      );
    } finally {
      setIsEnsuringModelGroups(false);
    }
  }
  async function updateProtocolExtension(allowed: boolean) {
    if (!result || !siteId) return;
    setAllowProtocolExtension(allowed);
    setIsEnsuringModelGroups(true);
    try {
      const nextResult = await requestPreview(
        modelGroupEnsureInputsFromResult(result.items),
        allowed,
      );
      setResult(nextResult);
      showModelGroupEnsureSkippedToast(nextResult, locale);
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
    } catch (error) {
      setAllowProtocolExtension(!allowed);
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN"
            ? "更新模型组预览失败"
            : "Failed to update model group preview",
        ),
      );
    } finally {
      setIsEnsuringModelGroups(false);
    }
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
    if (!result || !siteId) return;
    const selected = new Set(selectedKeys);
    const overrides = new Map(
      Object.entries(groupOverrides)
        .map(([key, value]) => [key, value.trim()] as const)
        .filter(([, value]) => value),
    );
    const models = result.items
      .filter(
        (item) =>
          canSubmitModelGroupEnsureItem(item) &&
          selected.has(modelGroupEnsureResultKey(item)),
      )
      .map((item) => modelGroupEnsureInputsFromResult([item], overrides)[0]);
    if (!models.length) {
      toast.info(
        locale === "zh-CN" ? "请选择要处理的模型" : "Select models to process",
      );
      return;
    }
    setIsEnsuringModelGroups(true);
    try {
      const nextResult = await apiRequest<ModelGroupEnsureFromSiteResponse>(
        "/admin/model-groups/ensure-from-site",
        {
          method: "POST",
          body: JSON.stringify({
            site_id: siteId,
            dry_run: false,
            allow_protocol_extension: allowProtocolExtension,
            models,
          } satisfies ModelGroupEnsureFromSitePayload),
        },
      );
      setModelGroupEnsureOpen(false);
      setSiteId("");
      setResult(null);
      setGroups([]);
      setAllowProtocolExtension(false);
      setSelectedKeys([]);
      toast.success(
        locale === "zh-CN"
          ? `已处理 ${nextResult.created_count + nextResult.updated_count} 项`
          : `Processed ${nextResult.created_count + nextResult.updated_count} items`,
      );
      await invalidateChannelData();
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN"
            ? "处理模型组失败"
            : "Failed to process model groups",
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
    openModelGroupEnsureDialog,
    updateTarget,
    updateProtocolExtension,
    toggleItem,
    confirm,
  };
}
