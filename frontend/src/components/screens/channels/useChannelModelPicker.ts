import { type Dispatch, type SetStateAction, useRef, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type {
  SiteModelFetchItem,
  SiteModelFetchPayload,
} from "@/lib/api/sites";
import { headerDraftToRules } from "@/lib/upstreamRules";
import { headerDraftsFromJson } from "./channelAdvancedJson";
import { activeBaseUrlValue } from "./channelForm";
import {
  activeSelectedCredentialIds,
  buildModels,
  canRunModelAction,
  existingPickerModelKeys,
  fallbackCredentialName,
  genericModelKey,
  groupPickerModels,
} from "./channelModels";
import type {
  FormProtocolConfig,
  FormState,
  Locale,
  PickerModelItem,
} from "./channelTypes";

/** Owns upstream catalog discovery and import into the channel form. */
export function useChannelModelPicker({
  form,
  setForm,
  locale,
}: {
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  locale: Locale;
}) {
  const [fetching, setFetching] = useState(false);
  const lastRunAtRef = useRef<Record<string, number>>({});

  async function requestUpstreamModels(
    configIndex: number,
  ): Promise<{ config: FormProtocolConfig; models: PickerModelItem[] } | null> {
    if (fetching) return null;
    const config = form.protocolConfigs[configIndex];
    if (!config) return null;
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
    if (!canRunModelAction(lastRunAtRef.current, `fetch:${configIndex}`)) {
      return null;
    }
    setFetching(true);
    try {
      const selected = new Set(credentialIds);
      const payload: SiteModelFetchPayload = {
        base_url: baseUrl.trim(),
        headers: headerDraftToRules(
          headerDraftsFromJson(form.headersJson) ?? [],
        ),
        proxy_mode: form.proxy_mode,
        channel_proxy: form.channel_proxy.trim(),
        match_regex: "",
        credentials: form.credentials
          .map((item, index) => ({
            id: item.id,
            name: item.name.trim() || fallbackCredentialName(index),
            api_key: item.api_key.trim(),
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
      setFetching(false);
    }
  }

  async function discoverRemoteCatalog(configIndex = 0) {
    const result = await requestUpstreamModels(configIndex);
    if (!result) return null;
    return {
      items: groupPickerModels(result.models),
      boundNames: new Set(
        result.config.models.map((model) => model.model_name),
      ),
    };
  }

  function importRemoteModels(items: PickerModelItem[]) {
    if (!items.length) return 0;
    let imported = 0;
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => {
        const existingKeys = existingPickerModelKeys(config);
        const newModels = items.flatMap((item) => {
          if (existingKeys.has(genericModelKey(item))) return [];
          return buildModels(
            config,
            [item.credential_id],
            item.model_name,
            ["auto"],
            "synced",
          );
        });
        imported += newModels.length;
        if (!newModels.length) return config;
        return {
          ...config,
          models: [...config.models, ...newModels],
          sync_targets: [
            ...config.sync_targets,
            ...newModels.flatMap((model) =>
              model.protocols.map((protocol) => ({
                credential_id: model.credential_id,
                model_name: model.model_name,
                protocol,
              })),
            ),
          ],
        };
      }),
    }));
    return imported;
  }

  return {
    fetching,
    discoverRemoteCatalog,
    importRemoteModels,
  };
}
