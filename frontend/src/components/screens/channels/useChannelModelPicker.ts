import { type Dispatch, type SetStateAction, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  SiteModelFetchItem,
  SiteModelFetchPayload,
  SiteModelProtocolDetectionPayload,
  SiteModelProtocolDetectionResult,
} from "@/lib/api/sites";
import {
  headerDraftToRules,
  paramOverrideDraftToRules,
} from "@/lib/upstreamRules";
import {
  headerDraftsFromJson,
  paramDraftsFromJson,
} from "./channelAdvancedJson";
import { activeBaseUrlValue, formHeaders } from "./channelForm";
import {
  protocolForEndpointKind,
  rebuildProtocolConfigs,
} from "./channelFormConversion";
import {
  acceptApiKeyDrafts,
  activeSelectedCredentialIds,
  aggregateModelGroupKey,
  credentialLabel,
  escapeModelName,
  fallbackCredentialName,
  formatCredentialTitle,
  mergeModelPatterns,
} from "./channelModels";
import type {
  FormProtocolConfig,
  FormState,
  Locale,
  PickerModelItem,
} from "./channelTypes";

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

// Models per detection request; each one may probe several protocols.
const DETECTION_CHUNK_SIZE = 8;

type ProtocolDetection = {
  /** Detected protocol by aggregate model key. */
  protocols: Map<string, ProtocolKind>;
  /** First reason a model or request went undetected. */
  error: string;
};

/** Detects the upstream protocol of each config × model, once per model name. */
async function detectProtocols(
  form: FormState,
  entries: Array<{
    protocolConfigId: string;
    credentialId: string;
    modelName: string;
  }>,
): Promise<ProtocolDetection> {
  const requests = new Map<
    string,
    { config: FormProtocolConfig; credentialId: string; modelNames: string[] }
  >();
  const seen = new Set<string>();
  for (const entry of entries) {
    const groupKey = aggregateModelGroupKey(
      { id: entry.protocolConfigId },
      entry.modelName,
    );
    const config = form.protocolConfigs.find(
      (item) => item.id === entry.protocolConfigId,
    );
    if (!config || seen.has(groupKey)) continue;
    seen.add(groupKey);
    const requestKey = JSON.stringify([config.id, entry.credentialId]);
    const request = requests.get(requestKey) ?? {
      config,
      credentialId: entry.credentialId,
      modelNames: [],
    };
    request.modelNames.push(entry.modelName);
    requests.set(requestKey, request);
  }

  const detection: ProtocolDetection = { protocols: new Map(), error: "" };
  for (const { config, credentialId, modelNames } of requests.values()) {
    const credentialIndex = form.credentials.findIndex(
      (item) => item.id === credentialId,
    );
    const credential = form.credentials[credentialIndex];
    const baseUrl = activeBaseUrlValue(form, config).trim();
    if (!credential?.api_key.trim() || !baseUrl) continue;
    const base = {
      base_url: baseUrl,
      endpoint_kind:
        form.base_urls.find((item) => item.id === config.base_url_id)?.kind ??
        "default",
      headers: formHeaders(form),
      proxy_mode: form.proxy_mode,
      channel_proxy: form.channel_proxy.trim(),
      param_override: paramOverrideDraftToRules(
        paramDraftsFromJson(form.paramsJson) ?? [],
      ),
      credential: {
        id: credential.id,
        name: credential.name.trim() || fallbackCredentialName(credentialIndex),
        api_key: credential.api_key.trim(),
      },
    } satisfies Omit<SiteModelProtocolDetectionPayload, "model_names">;
    for (
      let start = 0;
      start < modelNames.length;
      start += DETECTION_CHUNK_SIZE
    ) {
      try {
        const results = await apiRequest<SiteModelProtocolDetectionResult[]>(
          "/admin/site-model-protocol-detections",
          {
            method: "POST",
            body: JSON.stringify({
              ...base,
              model_names: modelNames.slice(
                start,
                start + DETECTION_CHUNK_SIZE,
              ),
            } satisfies SiteModelProtocolDetectionPayload),
          },
        );
        for (const result of results) {
          if (result.protocol) {
            detection.protocols.set(
              aggregateModelGroupKey(config, result.model_name),
              result.protocol,
            );
          } else {
            detection.error ||= result.error_message;
          }
        }
      } catch (error) {
        detection.error ||= getApiErrorMessage(error, "");
      }
    }
  }
  return detection;
}

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
  const [detecting, setDetecting] = useState(false);

  /** Fetches every base URL with each of its keys; failures only warn. */
  async function discoverRemoteCatalog(): Promise<RemoteModelCatalog | null> {
    if (fetching) return null;
    const drafted = acceptApiKeyDrafts(form);
    const editor = {
      ...drafted,
      protocolConfigs: rebuildProtocolConfigs(drafted),
    };
    setForm(editor);
    const headers = headerDraftToRules(
      headerDraftsFromJson(editor.headersJson) ?? [],
    );
    const targets = editor.protocolConfigs.flatMap((config) => {
      const credentialIds = new Set(
        activeSelectedCredentialIds(editor, config),
      );
      const baseUrl = activeBaseUrlValue(editor, config).trim();
      if (!credentialIds.size || !baseUrl) return [];
      const payload: SiteModelFetchPayload = {
        base_url: baseUrl,
        headers,
        proxy_mode: editor.proxy_mode,
        channel_proxy: editor.channel_proxy.trim(),
        credentials: editor.credentials
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
        editor.credentials.map((item, index) => [item.id, index] as const),
      );
      const items = results.flatMap((result, index) =>
        result.status === "fulfilled"
          ? result.value.map((item) => {
              const credentialIndex =
                credentialIndexById.get(item.credential_id) ?? -1;
              const credential = editor.credentials[credentialIndex];
              return {
                protocol_config_id: targets[index].protocolConfigId,
                credential_id: item.credential_id,
                model_name: item.model_name,
                context_window: item.context_window,
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
          editor.protocolConfigs.flatMap((config) =>
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

  /** 识别选中模型的上游协议后写入表格，并为对应 Key 追加精确规则。 */
  async function importRemoteModels(items: PickerModelItem[]) {
    const editor = { ...form, protocolConfigs: rebuildProtocolConfigs(form) };
    // 同一密钥只检测一次，避免专用地址把整个目录都判成自己的协议。
    const sources = new Map<string, PickerModelItem>();
    const sourcePriority = (item: PickerModelItem) => {
      const config = editor.protocolConfigs.find(
        (config) => config.id === item.protocol_config_id,
      );
      const kind = editor.base_urls.find(
        (url) => url.id === config?.base_url_id,
      )?.kind;
      return kind === "china" ? 2 : kind === "default" ? 1 : 0;
    };
    for (const item of items) {
      const generic = editor.protocolConfigs
        .filter((config) => config.credential_ids.includes(item.credential_id))
        .map((config) => ({ ...item, protocol_config_id: config.id }))
        .sort((left, right) => sourcePriority(right) - sourcePriority(left))[0];
      const source = generic && sourcePriority(generic) > 0 ? generic : item;
      const key = JSON.stringify([item.credential_id, item.model_name]);
      const current = sources.get(key);
      if (!current || sourcePriority(source) > sourcePriority(current))
        sources.set(key, source);
    }
    items = [...sources.values()];
    setDetecting(true);
    const detection = await detectProtocols(
      editor,
      items.map((item) => ({
        protocolConfigId: item.protocol_config_id,
        credentialId: item.credential_id,
        modelName: item.model_name,
      })),
    ).finally(() => setDetecting(false));
    const undetected = new Set(
      items
        .map((item) =>
          aggregateModelGroupKey(
            { id: item.protocol_config_id },
            item.model_name,
          ),
        )
        .filter((key) => !detection.protocols.has(key)),
    ).size;
    if (undetected) {
      toast.warning(
        locale === "zh-CN"
          ? `${undetected} 个模型未识别出协议，已按默认协议加入，可在模型列表中修改`
          : `${undetected} models got the default protocol; change it in the model list`,
        { description: detection.error || undefined },
      );
    }
    const additionsByCredential = new Map<string, string[]>();
    for (const item of items) {
      const list = additionsByCredential.get(item.credential_id) ?? [];
      list.push(escapeModelName(item.model_name));
      additionsByCredential.set(item.credential_id, list);
    }
    setForm((current) => {
      const next = {
        ...current,
        credentials: current.credentials.map((credential) => {
          const additions = additionsByCredential.get(credential.id);
          if (!additions) return credential;
          return {
            ...credential,
            model_pattern: mergeModelPatterns(
              credential.model_pattern,
              additions,
            ),
          };
        }),
        protocolConfigs: rebuildProtocolConfigs(current).map((config) => {
          const configItems = items.filter(
            (item) => item.protocol_config_id === config.id,
          );
          if (!configItems.length) return config;
          const fallbackProtocol = protocolForEndpointKind(
            current.base_urls.find((item) => item.id === config.base_url_id)
              ?.kind,
          );
          const existing = new Set(
            config.models.map((model) =>
              JSON.stringify([model.credential_id, model.model_name]),
            ),
          );
          const models = configItems.flatMap((item) => {
            const key = JSON.stringify([item.credential_id, item.model_name]);
            if (existing.has(key)) return [];
            existing.add(key);
            return [
              {
                credential_id: item.credential_id,
                model_name: item.model_name,
                enabled: true,
                protocols: [
                  detection.protocols.get(
                    aggregateModelGroupKey(config, item.model_name),
                  ) ?? fallbackProtocol,
                ],
                protocolIds: {},
                context_window: null,
                upstream_context_window: item.context_window,
              },
            ];
          });
          return { ...config, models: [...config.models, ...models] };
        }),
      };
      return { ...next, protocolConfigs: rebuildProtocolConfigs(next) };
    });
  }

  /** Re-detects the protocol of overview rows; undetected rows keep theirs. */
  async function detectModelProtocols(keys: string[]) {
    if (detecting || !keys.length) return;
    const selected = new Set(keys);
    const entries = form.protocolConfigs.flatMap((config) =>
      config.models
        .filter(
          (model) =>
            selected.has(aggregateModelGroupKey(config, model.model_name)) &&
            form.credentials.some(
              (item) => item.id === model.credential_id && item.api_key.trim(),
            ),
        )
        .map((model) => ({
          protocolConfigId: config.id,
          credentialId: model.credential_id,
          modelName: model.model_name,
        })),
    );
    setDetecting(true);
    const detection = await detectProtocols(form, entries).finally(() =>
      setDetecting(false),
    );
    const detected = detection.protocols.size;
    if (detected) {
      setForm((current) => {
        const next = {
          ...current,
          protocolConfigs: current.protocolConfigs.map((config) => ({
            ...config,
            models: config.models.map((model) => {
              const protocol = detection.protocols.get(
                aggregateModelGroupKey(config, model.model_name),
              );
              return protocol ? { ...model, protocols: [protocol] } : model;
            }),
          })),
        };
        return { ...next, protocolConfigs: rebuildProtocolConfigs(next) };
      });
      toast.success(
        locale === "zh-CN"
          ? `已识别 ${detected} 个模型的协议，保存后生效`
          : `Detected protocols for ${detected} models; they apply after saving`,
      );
    }
    const undetected = selected.size - detected;
    if (undetected) {
      toast.warning(
        locale === "zh-CN"
          ? `${undetected} 个模型未识别出协议，保持原协议`
          : `${undetected} models were not detected and keep their protocol`,
        { description: detection.error || undefined },
      );
    }
  }

  return {
    fetching,
    detecting,
    discoverRemoteCatalog,
    importRemoteModels,
    detectModelProtocols,
  };
}
