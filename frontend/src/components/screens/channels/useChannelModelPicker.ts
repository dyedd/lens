import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type {
  SiteModelFetchItem,
  SiteModelFetchPayload,
  SiteModelProtocolDetectionPayload,
  SiteModelProtocolDetectionResult,
} from "@/lib/api/sites";
import {
  credentialLabel,
  fallbackCredentialName,
  formatCredentialTitle,
} from "@/lib/credentialLabels";
import { headerDraftToRules } from "@/lib/upstreamRules";
import { headerDraftsFromJson } from "./channelAdvancedJson";
import {
  acceptApiKeyDrafts,
  activeBaseUrlValue,
  activeSelectedCredentialIds,
} from "./channelForm";
import { rebuildProtocolConfigs } from "./channelFormConversion";
import {
  aggregateModelGroupKey,
  escapeModelName,
  mergeModelPatterns,
  protocolConfigModelKey,
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

const DETECTION_CHUNK_SIZE = 1000;

/** Owns upstream catalog discovery and import into the channel form. */
export function useChannelModelPicker({
  form,
  setForm,
  sessionKey,
  locale,
}: {
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  sessionKey: string | null;
  locale: Locale;
}) {
  const [fetching, setFetching] = useState(false);
  const catalogSignal = useRef<AbortSignal | null>(null);
  const [detecting, setDetecting] = useState(false);
  const detectionController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (sessionKey === null) return;
    return () => {
      detectionController.current?.abort();
      detectionController.current = null;
      setDetecting(false);
    };
  }, [sessionKey]);

  /** Fetches every base URL with each of its keys; failures only warn. */
  async function discoverRemoteCatalog(
    signal: AbortSignal,
  ): Promise<RemoteModelCatalog | null> {
    if (signal.aborted) return null;
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
        endpoint_kind:
          editor.base_urls.find((item) => item.id === config.base_url_id)
            ?.kind ?? "default",
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
    catalogSignal.current = signal;
    setFetching(true);
    try {
      const results = await Promise.allSettled(
        targets.map((target) =>
          apiRequest<SiteModelFetchItem[]>("/admin/site-model-discoveries", {
            method: "POST",
            body: JSON.stringify(target.payload),
            signal,
          }),
        ),
      );
      if (signal.aborted) return null;
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
                protocol: item.protocol,
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
      if (catalogSignal.current === signal) {
        catalogSignal.current = null;
        setFetching(false);
      }
    }
  }

  function importRemoteModels(items: PickerModelItem[]) {
    if (detectionController.current || !items.length) return;
    const editor = { ...form, protocolConfigs: rebuildProtocolConfigs(form) };
    // 优先使用通用目录，避免专用地址把整个目录都归为同一协议。
    const sources = new Map<string, PickerModelItem>();
    const sourcePriority = (item: PickerModelItem) => {
      const config = editor.protocolConfigs.find(
        (config) => config.id === item.protocol_config_id,
      );
      const kind = editor.base_urls.find(
        (url) => url.id === config?.base_url_id,
      )?.kind;
      return kind === "china"
        ? 2
        : kind === "default" || kind === "protocol"
          ? 1
          : 0;
    };
    for (const item of items) {
      const key = JSON.stringify([item.credential_id, item.model_name]);
      const current = sources.get(key);
      if (!current || sourcePriority(item) > sourcePriority(current))
        sources.set(key, item);
    }
    items = [...sources.values()];
    const additionsByCredential = new Map<string, string[]>();
    for (const item of items) {
      const names = additionsByCredential.get(item.credential_id) ?? [];
      names.push(escapeModelName(item.model_name));
      additionsByCredential.set(item.credential_id, names);
    }
    const selectedContexts = new Map(
      items.map((item) => [
        JSON.stringify([item.credential_id, item.model_name]),
        item.context_window,
      ]),
    );
    setForm((current) => {
      const existing = new Set(
        current.protocolConfigs.flatMap((config) =>
          config.models.map((model) =>
            JSON.stringify([model.credential_id, model.model_name]),
          ),
        ),
      );
      const next = {
        ...current,
        credentials: current.credentials.map((credential) => {
          const additions = additionsByCredential.get(credential.id);
          return additions
            ? {
                ...credential,
                model_pattern: mergeModelPatterns(
                  credential.model_pattern,
                  additions,
                ),
              }
            : credential;
        }),
        protocolConfigs: rebuildProtocolConfigs(current).map((config) => {
          const models = config.models.map((model) => {
            const contextWindow = selectedContexts.get(
              JSON.stringify([model.credential_id, model.model_name]),
            );
            return model.context_window === null && contextWindow != null
              ? { ...model, context_window: contextWindow }
              : model;
          });
          const additions = items.flatMap((item) => {
            const key = JSON.stringify([item.credential_id, item.model_name]);
            if (item.protocol_config_id !== config.id || existing.has(key))
              return [];
            existing.add(key);
            return [
              {
                credential_id: item.credential_id,
                model_name: item.model_name,
                enabled: true,
                protocols: [item.protocol],
                modelIdsByProtocol: {},
                context_window: item.context_window,
                upstream_context_window: null,
              },
            ];
          });
          return { ...config, models: [...models, ...additions] };
        }),
      };
      return { ...next, protocolConfigs: rebuildProtocolConfigs(next) };
    });

    const contextNames = [
      ...new Set(
        items
          .filter((item) => item.context_window === null)
          .map((item) => item.model_name),
      ),
    ];
    if (!contextNames.length) return;
    const controller = new AbortController();
    detectionController.current = controller;
    setDetecting(true);
    const { signal } = controller;
    const progress = toast.loading(
      locale === "zh-CN"
        ? "正在后台识别上下文"
        : "Detecting context windows in the background",
    );
    const requests = Array.from(
      { length: Math.ceil(contextNames.length / DETECTION_CHUNK_SIZE) },
      (_, index) =>
        apiRequest<Record<string, number | null>>(
          "/admin/model-context-detections",
          {
            method: "POST",
            signal,
            body: JSON.stringify({
              model_names: contextNames.slice(
                index * DETECTION_CHUNK_SIZE,
                (index + 1) * DETECTION_CHUNK_SIZE,
              ),
            }),
          },
        ).then((windows) => {
          if (signal.aborted) return;
          setForm((current) => {
            if (signal.aborted) return current;
            return {
              ...current,
              protocolConfigs: current.protocolConfigs.map((config) => ({
                ...config,
                models: config.models.map((model) => {
                  const key = JSON.stringify([
                    model.credential_id,
                    model.model_name,
                  ]);
                  const contextWindow = windows[model.model_name];
                  return sources.has(key) &&
                    model.context_window === null &&
                    contextWindow != null
                    ? { ...model, context_window: contextWindow }
                    : model;
                }),
              })),
            };
          });
        }),
    );
    void Promise.allSettled(requests)
      .then((results) => {
        if (signal.aborted) return;
        const failure = results.find((result) => result.status === "rejected");
        if (failure)
          toast.warning(
            locale === "zh-CN"
              ? "部分上下文未能自动识别，可稍后重试"
              : "Some context windows could not be detected; retry later",
            { description: getApiErrorMessage(failure.reason, "") },
          );
      })
      .finally(() => {
        toast.dismiss(progress);
        if (detectionController.current === controller) {
          detectionController.current = null;
          setDetecting(false);
        }
      });
  }

  /** 用默认预选值更新所选模型，保留请求期间的手动修改。 */
  async function detectModelProtocols(keys: string[]) {
    if (detectionController.current || !keys.length) return;
    const selected = new Set(keys);
    const targets = form.protocolConfigs.flatMap((config) => {
      const names = [
        ...new Set(
          config.models
            .filter((model) =>
              selected.has(aggregateModelGroupKey(model.model_name)),
            )
            .map((model) => model.model_name),
        ),
      ];
      if (!names.length) return [];
      return [
        {
          config,
          names,
          kind:
            form.base_urls.find((url) => url.id === config.base_url_id)?.kind ??
            "default",
        },
      ];
    });
    if (!targets.length) return;
    const originals = new Map(
      form.protocolConfigs.flatMap((config) =>
        config.models.map(
          (model) =>
            [protocolConfigModelKey(config, model), model.protocols] as const,
        ),
      ),
    );
    const controller = new AbortController();
    detectionController.current = controller;
    setDetecting(true);
    const { signal } = controller;
    const requests = targets.flatMap(({ config, names, kind }) =>
      Array.from(
        { length: Math.ceil(names.length / DETECTION_CHUNK_SIZE) },
        (_, index) =>
          apiRequest<SiteModelProtocolDetectionResult[]>(
            "/admin/site-model-protocol-detections",
            {
              method: "POST",
              signal,
              body: JSON.stringify({
                endpoint_kind: kind,
                model_names: names.slice(
                  index * DETECTION_CHUNK_SIZE,
                  (index + 1) * DETECTION_CHUNK_SIZE,
                ),
              } satisfies SiteModelProtocolDetectionPayload),
            },
          ).then((values) => ({ configId: config.id, values })),
      ),
    );
    const results = await Promise.allSettled(requests).finally(() => {
      if (detectionController.current === controller) {
        detectionController.current = null;
        setDetecting(false);
      }
    });
    if (signal.aborted) return;
    const defaults = new Map<
      string,
      SiteModelProtocolDetectionResult["protocols"]
    >();
    const names = new Set<string>();
    for (const result of results) {
      if (result.status !== "fulfilled") continue;
      for (const item of result.value.values) {
        defaults.set(
          JSON.stringify([result.value.configId, item.model_name]),
          item.protocols,
        );
        names.add(item.model_name);
      }
    }
    if (defaults.size) {
      setForm((current) => {
        if (signal.aborted) return current;
        const next = {
          ...current,
          protocolConfigs: current.protocolConfigs.map((config) => ({
            ...config,
            models: config.models.map((model) => {
              const key = protocolConfigModelKey(config, model);
              const original = originals.get(key);
              const protocols = defaults.get(
                JSON.stringify([config.id, model.model_name]),
              );
              if (
                !original ||
                !protocols ||
                model.protocols.length !== original.length ||
                model.protocols.some((protocol) => !original.includes(protocol))
              )
                return model;
              return { ...model, protocols };
            }),
          })),
        };
        return { ...next, protocolConfigs: rebuildProtocolConfigs(next) };
      });
      toast.success(
        locale === "zh-CN"
          ? `已预选 ${names.size} 个模型的默认协议，保存后生效`
          : `Selected default protocols for ${names.size} models; save to apply`,
      );
    }
    const failure = results.find((result) => result.status === "rejected");
    if (failure)
      toast.warning(
        locale === "zh-CN"
          ? "部分模型协议未能自动预选，保留当前配置"
          : "Some default protocols could not be selected; current settings were kept",
        { description: getApiErrorMessage(failure.reason, "") },
      );
  }

  return {
    fetching,
    detecting,
    discoverRemoteCatalog,
    importRemoteModels,
    detectModelProtocols,
  };
}
