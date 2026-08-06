"use client";

import { useRef, useState, type Dispatch, type SetStateAction } from "react";
import { toast } from "sonner";
import {
  apiRequest,
  getApiErrorMessage,
  type ProtocolKind,
  type SiteModelFetchItem,
  type SiteModelFetchPayload,
} from "@/lib/api";
import {
  activeBaseUrlValue,
  classifyModelQueryInput,
  fallbackCredentialName,
  formHeaders,
  genericModelKey,
  groupPickerModels,
  mergeSyncedModels,
  resolvePickerModelProtocols,
  type FormModel,
  type FormProtocolConfig,
  type FormState,
  type Locale,
  type PickerModelItem,
} from "./channelShared";
import {
  activeSelectedCredentialIds,
  buildManualModels,
  canRunModelAction,
} from "./channelModelPickerUtils";

/** Owns manual model additions, discovery, and picker selection. */
export function useChannelModelPicker({
  form,
  setForm,
  locale,
}: {
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  locale: Locale;
}) {
  const [fetchingProtocolConfigIndex, setFetchingProtocolConfigIndex] =
    useState<number | null>(null);
  const [modelPickerProtocolConfigIndex, setModelPickerProtocolConfigIndex] =
    useState<number | null>(null);
  const [availableModels, setAvailableModels] = useState<PickerModelItem[]>([]);
  const [pickerSelectedModelKeys, setPickerSelectedModelKeys] = useState<
    string[]
  >([]);
  const [pickerImportProtocols, setPickerImportProtocols] = useState<
    ProtocolKind[]
  >([]);
  const [pickerModelProtocols, setPickerModelProtocols] = useState<
    Record<string, ProtocolKind[]>
  >({});
  const lastRunAtRef = useRef<Record<string, number>>({});

  function addManualProtocolConfigModel(configIndex: number) {
    const config = form.protocolConfigs[configIndex];
    const modelName = config?.manual_model_name.trim() ?? "";
    if (!config || !modelName) return;
    const credentialIds = activeSelectedCredentialIds(form, config);
    if (!credentialIds.length) {
      toast.error(
        locale === "zh-CN"
          ? "请选择至少一个可用密钥"
          : "Select at least one available key",
      );
      return;
    }
    if (classifyModelQueryInput(modelName) !== "plain") {
      toast.error(
        locale === "zh-CN"
          ? "正则或空值不能直接添加模型"
          : "Regex or empty input cannot be added directly",
      );
      return;
    }
    const protocols = Array.from(new Set(config.manual_protocols));
    if (!protocols.length) {
      toast.error(
        locale === "zh-CN"
          ? "请先选择手动添加模型的客户端协议"
          : "Select client protocols for manually added models first",
      );
      return;
    }
    if (!canRunModelAction(lastRunAtRef.current, `add:${configIndex}`)) return;
    const newModels = buildManualModels(
      config,
      credentialIds,
      modelName,
      protocols,
    );
    if (!newModels.length) {
      toast.info(locale === "zh-CN" ? "模型已存在" : "Model already exists");
      return;
    }
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((item, index) =>
        index === configIndex
          ? {
              ...item,
              manual_model_name: "",
              expanded: true,
              models: [...item.models, ...newModels],
            }
          : item,
      ),
    }));
  }
  /**
   * Validates a protocol config and fetches its upstream models.
   *
   * Returns null when validation fails, the action is throttled, or the
   * request errors; callers only proceed on a resolved result.
   */
  async function requestUpstreamModels(
    configIndex: number,
    actionKey: string,
  ): Promise<{ config: FormProtocolConfig; models: PickerModelItem[] } | null> {
    if (fetchingProtocolConfigIndex !== null) return null;
    const config = form.protocolConfigs[configIndex];
    if (!config) return null;
    const protocols = Array.from(new Set(config.manual_protocols));
    if (!protocols.length) {
      toast.error(
        locale === "zh-CN"
          ? "请先选择本次获取的客户端协议"
          : "Select client protocols for this fetch first",
      );
      return null;
    }
    const credentialIds = activeSelectedCredentialIds(form, config);
    if (!credentialIds.length) {
      toast.error(
        locale === "zh-CN"
          ? "请选择至少一个可用密钥"
          : "Select at least one available key",
      );
      return null;
    }
    const baseUrl = activeBaseUrlValue(form, config);
    if (!baseUrl.trim()) {
      toast.error(locale === "zh-CN" ? "地址为空" : "Base URL is empty");
      return null;
    }
    if (!canRunModelAction(lastRunAtRef.current, `${actionKey}:${configIndex}`))
      return null;
    setFetchingProtocolConfigIndex(configIndex);
    try {
      const selected = new Set(credentialIds);
      const payload: SiteModelFetchPayload = {
        base_url: baseUrl.trim(),
        headers: formHeaders(config),
        proxy_mode: config.proxy_mode,
        channel_proxy: config.channel_proxy.trim(),
        match_regex: config.match_regex.trim(),
        credentials: form.credentials
          .map((item, index) => ({
            id: item.id,
            name: item.name.trim() || fallbackCredentialName(index),
            api_key: item.api_key.trim(),
            enabled: item.enabled,
          }))
          .filter((item) => item.api_key && selected.has(item.id)),
        credential_ids: credentialIds,
      };
      const models = await apiRequest<SiteModelFetchItem[]>(
        "/admin/site-model-discoveries",
        { method: "POST", body: JSON.stringify(payload) },
      );
      return {
        config,
        models: models.map((item) => ({
          credential_id: item.credential_id,
          credential_name: item.credential_name,
          model_name: item.model_name,
        })),
      };
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "获取模型失败" : "Failed to fetch models",
        ),
      );
      return null;
    } finally {
      setFetchingProtocolConfigIndex(null);
    }
  }
  async function fetchProtocolModels(configIndex: number) {
    const result = await requestUpstreamModels(configIndex, "fetch");
    if (!result) return;
    setAvailableModels(result.models);
    setPickerSelectedModelKeys([]);
    setPickerImportProtocols(
      Array.from(new Set(result.config.manual_protocols)),
    );
    setPickerModelProtocols({});
    setModelPickerProtocolConfigIndex(configIndex);
    toast.success(
      locale === "zh-CN"
        ? `已获取 ${result.models.length} 个可选模型`
        : `Fetched ${result.models.length} available models`,
    );
  }
  /** Replaces the synced model set with the upstream models matching the filter. */
  async function syncAllProtocolModels(configIndex: number) {
    const result = await requestUpstreamModels(configIndex, "sync");
    if (!result) return;
    if (!result.models.length) {
      toast.info(
        locale === "zh-CN"
          ? "上游没有匹配的模型，未做改动"
          : "No upstream models matched the filter; nothing changed",
      );
      return;
    }
    const fetched = groupPickerModels(result.models);
    const { models: nextModels, removedCount } = mergeSyncedModels(
      result.config.models,
      fetched,
      Array.from(new Set(result.config.manual_protocols)),
    );
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((item, index) =>
        index === configIndex
          ? { ...item, expanded: true, models: nextModels }
          : item,
      ),
    }));
    toast.success(
      locale === "zh-CN"
        ? `已同步 ${fetched.length} 个模型${removedCount ? `，移除 ${removedCount} 个上游已下架的模型` : ""}`
        : `Synced ${fetched.length} models${removedCount ? `, removed ${removedCount} no longer upstream` : ""}`,
    );
  }
  function closeModelPicker() {
    setModelPickerProtocolConfigIndex(null);
    setAvailableModels([]);
    setPickerSelectedModelKeys([]);
    setPickerImportProtocols([]);
    setPickerModelProtocols({});
  }
  function applyModelSelection(keys: string[]) {
    if (modelPickerProtocolConfigIndex === null) return;
    const config = form.protocolConfigs[modelPickerProtocolConfigIndex];
    if (!config) return;
    const protocolsForKey = (key: string) =>
      Array.from(
        new Set(
          resolvePickerModelProtocols(
            key,
            pickerModelProtocols,
            pickerImportProtocols,
          ),
        ),
      );
    const selected = new Set(keys);
    const selectedModels = groupPickerModels(
      availableModels.filter((item) => selected.has(genericModelKey(item))),
    );
    if (!selectedModels.length) {
      toast.info(locale === "zh-CN" ? "未选择模型" : "No models selected");
      closeModelPicker();
      return;
    }
    if (
      selectedModels.some(
        (model) => !protocolsForKey(genericModelKey(model)).length,
      )
    ) {
      toast.error(
        locale === "zh-CN"
          ? "请为所有选中模型选择协议"
          : "Select protocols for every selected model",
      );
      return;
    }
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((item, index) => {
        if (index !== modelPickerProtocolConfigIndex) return item;
        return {
          ...item,
          expanded: true,
          models: [
            ...item.models.filter(
              (model) => !selected.has(genericModelKey(model)),
            ),
            ...selectedModels.map((model) => {
              const key = genericModelKey(model);
              const existingModels = item.models.filter(
                (candidate) => genericModelKey(candidate) === key,
              );
              return {
                protocols: protocolsForKey(key),
                protocolIds: existingModels.reduce<FormModel["protocolIds"]>(
                  (ids, candidate) => ({
                    ...ids,
                    ...candidate.protocolIds,
                  }),
                  {},
                ),
                credential_id: model.credential_id,
                model_name: model.model_name,
                enabled: true,
                source: "manual" as const,
              };
            }),
          ],
        };
      }),
    }));
    closeModelPicker();
    toast.success(
      locale === "zh-CN"
        ? `已选择 ${selectedModels.length} 个模型`
        : `Selected ${selectedModels.length} models`,
    );
  }
  return {
    fetchingProtocolConfigIndex,
    modelPickerProtocolConfigIndex,
    availableModels,
    pickerSelectedModelKeys,
    setPickerSelectedModelKeys,
    pickerImportProtocols,
    setPickerImportProtocols,
    pickerModelProtocols,
    setPickerModelProtocols,
    addManualProtocolConfigModel,
    fetchProtocolModels,
    syncAllProtocolModels,
    closeModelPicker,
    applyModelSelection,
  };
}
