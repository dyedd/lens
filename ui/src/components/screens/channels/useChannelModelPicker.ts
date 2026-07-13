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
  isValidModelQueryRegex,
  resolvePickerModelProtocols,
  safeText,
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
              match_regex: "",
              auto_sync_enabled: false,
              expanded: true,
              models: [...item.models, ...newModels],
            }
          : item,
      ),
    }));
  }
  async function fetchProtocolModels(configIndex: number) {
    if (fetchingProtocolConfigIndex !== null) return;
    const config = form.protocolConfigs[configIndex];
    if (!config) return;
    const query = config.manual_model_name.trim();
    const kind = classifyModelQueryInput(query);
    if (kind === "plain") {
      toast.error(
        locale === "zh-CN"
          ? "普通模型名不能获取更多"
          : "Plain model names cannot fetch more",
      );
      return;
    }
    if (kind === "regex" && !isValidModelQueryRegex(query)) {
      toast.error(locale === "zh-CN" ? "正则无效" : "Invalid regex");
      return;
    }
    const protocols = Array.from(new Set(config.manual_protocols));
    if (!protocols.length) {
      toast.error(
        locale === "zh-CN"
          ? "请先选择本次获取的客户端协议"
          : "Select client protocols for this fetch first",
      );
      return;
    }
    const credentialIds = activeSelectedCredentialIds(form, config);
    if (!credentialIds.length) {
      toast.error(
        locale === "zh-CN"
          ? "请选择至少一个可用密钥"
          : "Select at least one available key",
      );
      return;
    }
    const baseUrl = activeBaseUrlValue(form, config);
    if (!safeText(baseUrl).trim()) {
      toast.error(locale === "zh-CN" ? "地址为空" : "Base URL is empty");
      return;
    }
    if (!canRunModelAction(lastRunAtRef.current, `fetch:${configIndex}`))
      return;
    setFetchingProtocolConfigIndex(configIndex);
    try {
      const selected = new Set(credentialIds);
      const payload: SiteModelFetchPayload = {
        base_url: safeText(baseUrl).trim(),
        headers: formHeaders(config),
        proxy_mode: config.proxy_mode,
        channel_proxy: config.channel_proxy.trim(),
        match_regex: kind === "regex" ? query : "",
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
      setAvailableModels(
        models.map((item) => ({
          credential_id: item.credential_id,
          credential_name: item.credential_name,
          model_name: item.model_name,
        })),
      );
      setPickerSelectedModelKeys([]);
      setPickerImportProtocols(protocols);
      setPickerModelProtocols({});
      setModelPickerProtocolConfigIndex(configIndex);
      toast.success(
        locale === "zh-CN"
          ? `已获取 ${models.length} 个可选模型`
          : `Fetched ${models.length} available models`,
      );
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          locale === "zh-CN" ? "获取模型失败" : "Failed to fetch models",
        ),
      );
    } finally {
      setFetchingProtocolConfigIndex(null);
    }
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
    const existing = new Set(config.models.map(genericModelKey));
    const newModels = groupPickerModels(
      availableModels.filter((item) => selected.has(genericModelKey(item))),
    ).filter((model) => !existing.has(genericModelKey(model)));
    if (!newModels.length) {
      toast.info(locale === "zh-CN" ? "模型已存在" : "Model already exists");
      closeModelPicker();
      return;
    }
    if (
      newModels.some((model) => !protocolsForKey(genericModelKey(model)).length)
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
      protocolConfigs: current.protocolConfigs.map((item, index) =>
        index !== modelPickerProtocolConfigIndex
          ? item
          : {
              ...item,
              expanded: true,
              models: [
                ...item.models,
                ...newModels.map((model) => ({
                  id: null,
                  protocols: protocolsForKey(genericModelKey(model)),
                  protocolIds: {},
                  credential_id: model.credential_id,
                  model_name: model.model_name,
                  enabled: true,
                })),
              ],
            },
      ),
    }));
    closeModelPicker();
    toast.success(
      locale === "zh-CN"
        ? `已加入 ${newModels.length} 个模型`
        : `Added ${newModels.length} models`,
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
    closeModelPicker,
    applyModelSelection,
  };
}
