import { type Dispatch, type SetStateAction, useRef, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  SiteModelFetchItem,
  SiteModelFetchPayload,
} from "@/lib/api/sites";
import {
  activeBaseUrlValue,
  classifyModelQueryInput,
  formHeaders,
} from "./channelFormUtils";
import { fallbackCredentialName } from "./channelLabels";
import {
  activeSelectedCredentialIds,
  buildModels,
  canRunModelAction,
  existingPickerModelKeys,
} from "./channelModelPickerUtils";
import {
  genericModelKey,
  groupPickerModels,
  resolvePickerModelProtocols,
} from "./channelModelUtils";
import type {
  FormModel,
  FormProtocolConfig,
  FormState,
  Locale,
  PickerModelItem,
} from "./channelTypes";

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
          ? "请先选择手动添加模型的上游协议"
          : "Select upstream protocols for manually added models first",
      );
      return;
    }
    if (!canRunModelAction(lastRunAtRef.current, `add:${configIndex}`)) return;
    const newModels = buildModels(
      config,
      credentialIds,
      modelName,
      protocols,
      config.sync_new_models ? "synced" : "manual",
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
              sync_targets: [
                ...item.sync_targets.filter(
                  (target) =>
                    !newModels.some(
                      (model) =>
                        genericModelKey(model) === genericModelKey(target),
                    ),
                ),
                ...(item.sync_new_models
                  ? [
                      ...newModels.flatMap((model) =>
                        model.protocols.map((protocol) => ({
                          credential_id: model.credential_id,
                          model_name: model.model_name,
                          protocol,
                        })),
                      ),
                    ]
                  : []),
              ],
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
  ): Promise<{ config: FormProtocolConfig; models: PickerModelItem[] } | null> {
    if (fetchingProtocolConfigIndex !== null) return null;
    const config = form.protocolConfigs[configIndex];
    if (!config) return null;
    const protocols = Array.from(new Set(config.manual_protocols));
    if (!protocols.length) {
      toast.error(
        locale === "zh-CN"
          ? "请先选择本次获取的上游协议"
          : "Select upstream protocols for this fetch first",
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
    if (!canRunModelAction(lastRunAtRef.current, `fetch:${configIndex}`))
      return null;
    setFetchingProtocolConfigIndex(configIndex);
    try {
      const selected = new Set(credentialIds);
      const payload: SiteModelFetchPayload = {
        base_url: baseUrl.trim(),
        headers: formHeaders(config),
        proxy_mode: config.proxy_mode,
        channel_proxy: config.channel_proxy.trim(),
        match_regex: config.model_filter.trim(),
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
      setForm((current) => ({
        ...current,
        protocolConfigs: current.protocolConfigs.map((item, index) =>
          index === configIndex ? { ...item, model_filter: "" } : item,
        ),
      }));
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
    const result = await requestUpstreamModels(configIndex);
    if (!result) return;
    const existingKeys = existingPickerModelKeys(result.config);
    const fetchedModels = groupPickerModels(result.models);
    const selectableModels = fetchedModels.filter(
      (model) => !existingKeys.has(genericModelKey(model)),
    );
    const fetchedNameCount = new Set(
      fetchedModels.map((model) => model.model_name),
    ).size;
    const selectableNameCount = new Set(
      selectableModels.map((model) => model.model_name),
    ).size;
    const hiddenCount = fetchedNameCount - selectableNameCount;
    if (!selectableModels.length) {
      toast.info(
        result.models.length
          ? locale === "zh-CN"
            ? "获取到的模型均已在总览中"
            : "Fetched models are already in the overview"
          : locale === "zh-CN"
            ? "未获取到可选模型"
            : "No models fetched",
      );
      return;
    }
    setAvailableModels(selectableModels);
    setPickerSelectedModelKeys([]);
    setPickerImportProtocols(
      Array.from(new Set(result.config.manual_protocols)),
    );
    setPickerModelProtocols({});
    setModelPickerProtocolConfigIndex(configIndex);
    toast.success(
      hiddenCount
        ? locale === "zh-CN"
          ? `已获取 ${selectableNameCount} 个可选模型，已隐藏 ${hiddenCount} 个已在总览中的模型`
          : `Fetched ${selectableNameCount} available models, hid ${hiddenCount} already in the overview`
        : locale === "zh-CN"
          ? `已获取 ${selectableNameCount} 个可选模型`
          : `Fetched ${selectableNameCount} available models`,
    );
  }
  function closeModelPicker() {
    setModelPickerProtocolConfigIndex(null);
    setAvailableModels([]);
    setPickerSelectedModelKeys([]);
    setPickerImportProtocols([]);
    setPickerModelProtocols({});
  }
  /**
   * Toggles a selection entry: a model name covers every key at once, while
   * a "credential:model" entry only covers that key from an expanded row.
   */
  function togglePickerModelSelection(key: string) {
    setPickerSelectedModelKeys((current) => {
      if (current.includes(key)) {
        return current.filter((item) => item !== key);
      }
      const memberKeys = availableModels
        .filter((item) => item.model_name === key)
        .map(genericModelKey);
      if (memberKeys.length <= 1) return [...current, key];
      const withoutMembers = current.filter(
        (item) => !memberKeys.includes(item),
      );
      return [...withoutMembers, key];
    });
  }
  function applyModelSelection(keys: string[]) {
    if (modelPickerProtocolConfigIndex === null) return;
    const config = form.protocolConfigs[modelPickerProtocolConfigIndex];
    if (!config) return;
    const protocolsForName = (modelName: string) =>
      Array.from(
        new Set(
          resolvePickerModelProtocols(
            modelName,
            pickerModelProtocols,
            pickerImportProtocols,
          ),
        ),
      );
    // Selection holds model names for whole-model picks and
    // "credential:model" keys for single-key picks from an expanded row.
    const memberKeySet = new Set(availableModels.map(genericModelKey));
    const selectedNames = new Set(keys.filter((key) => !memberKeySet.has(key)));
    const selectedMemberKeys = new Set(
      keys.filter((key) => memberKeySet.has(key)),
    );
    const existingKeys = existingPickerModelKeys(config);
    const selectedModels = groupPickerModels(
      availableModels.filter(
        (item) =>
          !existingKeys.has(genericModelKey(item)) &&
          (selectedNames.has(item.model_name) ||
            selectedMemberKeys.has(genericModelKey(item))),
      ),
    );
    if (!selectedModels.length) {
      toast.info(locale === "zh-CN" ? "未选择模型" : "No models selected");
      closeModelPicker();
      return;
    }
    if (
      selectedModels.some((model) => !protocolsForName(model.model_name).length)
    ) {
      toast.error(
        locale === "zh-CN"
          ? "请为所有选中模型选择协议"
          : "Select protocols for every selected model",
      );
      return;
    }
    const selectedKeys = new Set(selectedModels.map(genericModelKey));
    const selectedNameCount = new Set(
      selectedModels.map((model) => model.model_name),
    ).size;
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((item, index) => {
        if (index !== modelPickerProtocolConfigIndex) return item;
        return {
          ...item,
          expanded: true,
          models: [
            ...item.models.filter(
              (model) => !selectedKeys.has(genericModelKey(model)),
            ),
            ...selectedModels.map((model) => {
              const key = genericModelKey(model);
              const existingModels = item.models.filter(
                (candidate) => genericModelKey(candidate) === key,
              );
              const source: FormModel["source"] = item.sync_new_models
                ? "synced"
                : "manual";
              return {
                protocols: protocolsForName(model.model_name),
                protocolIds: existingModels.reduce<FormModel["protocolIds"]>(
                  (ids, candidate) => {
                    Object.assign(ids, candidate.protocolIds);
                    return ids;
                  },
                  {},
                ),
                credential_id: model.credential_id,
                model_name: model.model_name,
                enabled: true,
                source,
              };
            }),
          ],
          sync_targets: [
            ...item.sync_targets.filter(
              (target) => !selectedKeys.has(genericModelKey(target)),
            ),
            ...(item.sync_new_models
              ? selectedModels.flatMap((model) =>
                  protocolsForName(model.model_name).map((protocol) => ({
                    credential_id: model.credential_id,
                    model_name: model.model_name,
                    protocol,
                  })),
                )
              : []),
          ],
        };
      }),
    }));
    closeModelPicker();
    toast.success(
      locale === "zh-CN"
        ? `已选择 ${selectedNameCount} 个模型`
        : `Selected ${selectedNameCount} models`,
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
    togglePickerModelSelection,
    applyModelSelection,
  };
}
