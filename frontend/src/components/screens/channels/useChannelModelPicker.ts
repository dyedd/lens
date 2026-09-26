import { type Dispatch, type SetStateAction, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type {
  SiteModelFetchItem,
  SiteModelFetchPayload,
} from "@/lib/api/sites";
import { headerDraftToRules } from "@/lib/upstreamRules";
import { headerDraftsFromJson } from "./channelAdvancedJson";
import { activeBaseUrlValue } from "./channelForm";
import { rebuildProtocolConfigs } from "./channelFormConversion";
import {
  activeSelectedCredentialIds,
  buildModels,
  credentialLabel,
  fallbackCredentialName,
  formatCredentialTitle,
} from "./channelModels";
import type { FormState, Locale, PickerModelItem } from "./channelTypes";

export type RemoteModelItem = PickerModelItem & {
  credentialName: string;
  /** Key label plus masked value. */
  credentialTitle: string;
  baseUrl: string;
};

export type RemoteModelCatalog = {
  items: RemoteModelItem[];
  boundNames: Set<string>;
  /** Distinct keys queried across every URL. */
  credentialCount: number;
  hasMultipleBaseUrls: boolean;
};

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

  /** Fetches every base URL with each of its keys; failures only warn. */
  async function discoverRemoteCatalog(): Promise<RemoteModelCatalog | null> {
    if (fetching) return null;
    const headers = headerDraftToRules(
      headerDraftsFromJson(form.headersJson) ?? [],
    );
    const targets = rebuildProtocolConfigs(form).flatMap((config) => {
      const credentialIds = new Set(activeSelectedCredentialIds(form, config));
      const baseUrl = activeBaseUrlValue(form, config).trim();
      if (!credentialIds.size || !baseUrl) return [];
      const payload: SiteModelFetchPayload = {
        base_url: baseUrl,
        headers,
        proxy_mode: form.proxy_mode,
        channel_proxy: form.channel_proxy.trim(),
        match_regex: "",
        credentials: form.credentials
          .map((item, index) => ({
            id: item.id,
            name: item.name.trim() || fallbackCredentialName(index),
            api_key: item.api_key.trim(),
          }))
          .filter((item) => item.api_key && credentialIds.has(item.id)),
        credential_ids: [...credentialIds],
      };
      return [{ protocolConfigId: config.id, baseUrl, payload }];
    });
    if (!targets.length) {
      toast.error(
        locale === "zh-CN"
          ? "请先填写渠道地址和 API Key"
          : "Enter a channel URL and API key first",
      );
      return null;
    }
    setFetching(true);
    try {
      const results = await Promise.allSettled(
        targets.map((target) =>
          apiRequest<SiteModelFetchItem[]>("/admin/site-model-discoveries", {
            method: "POST",
            body: JSON.stringify(target.payload),
          }),
        ),
      );
      const credentialIndexById = new Map(
        form.credentials.map((item, index) => [item.id, index] as const),
      );
      const items = results.flatMap((result, index) =>
        result.status === "fulfilled"
          ? result.value.map((item) => {
              const credentialIndex =
                credentialIndexById.get(item.credential_id) ?? -1;
              const credential = form.credentials[credentialIndex];
              return {
                protocol_config_id: targets[index].protocolConfigId,
                credential_id: item.credential_id,
                model_name: item.model_name,
                credentialName: credential
                  ? credentialLabel(credential, credentialIndex, locale)
                  : item.credential_name,
                credentialTitle: credential
                  ? formatCredentialTitle(credential, credentialIndex, locale)
                  : item.credential_name,
                baseUrl: targets[index].baseUrl,
              };
            })
          : [],
      );
      const failure = results.find((result) => result.status === "rejected");
      if (failure) {
        const message = getApiErrorMessage(
          failure.reason,
          locale === "zh-CN" ? "获取模型失败" : "Failed to fetch models",
        );
        if (!items.length) {
          toast.error(message);
          return null;
        }
        toast.warning(
          locale === "zh-CN"
            ? "部分地址获取失败，已显示其余结果"
            : "Some URLs failed; showing the rest",
          { description: message },
        );
      }
      return {
        items,
        boundNames: new Set(
          form.protocolConfigs.flatMap((config) =>
            config.models.map((model) => model.model_name),
          ),
        ),
        credentialCount: new Set(
          targets.flatMap((target) => target.payload.credential_ids),
        ).size,
        hasMultipleBaseUrls: targets.length > 1,
      };
    } finally {
      setFetching(false);
    }
  }

  /** Adds picked upstream models as manual models of the keys serving them. */
  function importRemoteModels(items: PickerModelItem[]) {
    let imported = 0;
    const protocolConfigs = rebuildProtocolConfigs(form).map((config) => {
      const newModels = items
        .filter((item) => item.protocol_config_id === config.id)
        .flatMap((item) =>
          buildModels(
            config,
            [item.credential_id],
            item.model_name,
            ["auto"],
            "manual",
          ),
        );
      imported += newModels.length;
      return newModels.length
        ? { ...config, models: [...config.models, ...newModels] }
        : config;
    });
    setForm((current) => ({ ...current, protocolConfigs }));
    return imported;
  }

  return {
    fetching,
    discoverRemoteCatalog,
    importRemoteModels,
  };
}
