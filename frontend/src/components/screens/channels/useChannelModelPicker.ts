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
import { acceptApiKeyDrafts } from "./channelForm";
import {
  endpointSupportsProtocol,
  rebuildProtocolConfigs,
} from "./channelFormConversion";
import {
  aggregateModelGroupKey,
  escapeModelName,
  mergeModelPatterns,
  modelSourceKey,
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
  boundSources: Set<string>;
  /** Distinct keys queried across every URL. */
  credentialCount: number;
};

const DETECTION_CHUNK_SIZE = 1000;

type CredentialModelRule = { credentialId: string; pattern: string };

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
    rule?: CredentialModelRule,
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
    const targetsBySource = new Map<
      string,
      {
        configs: typeof editor.protocolConfigs;
        payload: SiteModelFetchPayload;
      }
    >();
    for (const config of editor.protocolConfigs) {
      const address = editor.base_urls.find(
        (url) => url.id === config.base_url_id,
      )!;
      for (const credentialId of config.credential_ids) {
        if (rule && credentialId !== rule.credentialId) continue;
        const index = editor.credentials.findIndex(
          (item) => item.id === credentialId,
        );
        const credential = editor.credentials[index];
        const source =
          editor.base_urls.find(
            (url) =>
              url.kind === "models" &&
              url.url.trim() &&
              (credential.base_url_ids === null ||
                credential.base_url_ids.includes(url.id)),
          ) ?? address;
        const key = JSON.stringify([source.id, credentialId]);
        const existing = targetsBySource.get(key);
        if (existing) {
          existing.configs.push(config);
          continue;
        }
        targetsBySource.set(key, {
          configs: [config],
          payload: {
            base_url_id: source.id,
            base_url: source.url.trim(),
            endpoint_kind: source.kind,
            ...(rule ? { model_pattern: rule.pattern } : {}),
            headers,
            proxy_mode: editor.proxy_mode,
            channel_proxy: editor.channel_proxy.trim(),
            credentials: [
              {
                id: credential.id,
                name: credential.name.trim() || fallbackCredentialName(index),
                api_key: credential.api_key.trim(),
                base_url_ids: credential.base_url_ids,
              },
            ],
            credential_ids: [credential.id],
          },
        });
      }
    }
    const targets = [...targetsBySource.values()];
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
      const items: RemoteModelItem[] = results.flatMap((result, index) =>
        result.status === "fulfilled"
          ? result.value.flatMap((item) => {
              const credentialIndex = credentialIndexById.get(
                item.credential_id,
              )!;
              const credential = editor.credentials[credentialIndex];
              return targets[index].configs.flatMap((config) => {
                const address = editor.base_urls.find(
                  (url) => url.id === config.base_url_id,
                )!;
                const existing = config.models.find(
                  (model) =>
                    model.credential_id === item.credential_id &&
                    model.model_name === item.model_name,
                );
                const protocols =
                  targets[index].payload.endpoint_kind === "models"
                    ? (existing?.protocols ?? [item.protocol]).filter(
                        (protocol) =>
                          endpointSupportsProtocol(address.kind, [protocol]),
                      )
                    : [item.protocol];
                return protocols.map((protocol) => ({
                  ...item,
                  protocol,
                  protocol_config_id: config.id,
                  credentialName: credentialLabel(
                    credential,
                    credentialIndex,
                    locale,
                  ),
                  credentialTitle: formatCredentialTitle(
                    credential,
                    credentialIndex,
                    locale,
                  ),
                  baseUrl: address.url,
                }));
              });
            })
          : [],
      );
      const failure = results.find((result) => result.status === "rejected");
      if (failure) {
        const message = getApiErrorMessage(
          failure.reason,
          locale === "zh-CN" ? "获取模型失败" : "Failed to fetch models",
        );
        if (rule || !items.length) {
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
        items: [
          ...new Map(
            items.map((item) => [modelSourceKey(item), item]),
          ).values(),
        ],
        boundSources: new Set(
          editor.protocolConfigs.flatMap((config) =>
            config.models.flatMap((model) =>
              model.protocols.map((protocol) =>
                modelSourceKey({
                  ...model,
                  protocol_config_id: config.id,
                  protocol,
                }),
              ),
            ),
          ),
        ),
        credentialCount: new Set(
          targets.flatMap((target) => target.payload.credential_ids),
        ).size,
      };
    } finally {
      if (catalogSignal.current === signal) {
        catalogSignal.current = null;
        setFetching(false);
      }
    }
  }

  function importRemoteModels(
    items: PickerModelItem[],
    rule?: CredentialModelRule,
  ) {
    if (detectionController.current || (!items.length && !rule)) return;
    items = [
      ...new Map(items.map((item) => [modelSourceKey(item), item])).values(),
    ];
    const sources = new Set(
      items.map((item) =>
        protocolConfigModelKey({ id: item.protocol_config_id }, item),
      ),
    );
    const additionsByCredential = new Map<string, string[]>();
    for (const item of items) {
      const names = additionsByCredential.get(item.credential_id) ?? [];
      names.push(escapeModelName(item.model_name));
      additionsByCredential.set(item.credential_id, names);
    }
    const existingSources = new Set(
      form.protocolConfigs.flatMap((config) =>
        config.models.map((model) => protocolConfigModelKey(config, model)),
      ),
    );
    const newModels = items.filter(
      (item) =>
        !existingSources.has(
          protocolConfigModelKey({ id: item.protocol_config_id }, item),
        ),
    );
    const addedSources = new Set(
      newModels.map((item) =>
        protocolConfigModelKey({ id: item.protocol_config_id }, item),
      ),
    );
    setForm((current) => {
      const configs = rebuildProtocolConfigs(current);
      return {
        ...current,
        credentials: current.credentials.map((credential) => {
          if (credential.id === rule?.credentialId)
            return { ...credential, model_pattern: rule.pattern };
          const additions = additionsByCredential.get(credential.id);
          return additions
            ? {
                ...credential,
                model_pattern: mergeModelPatterns(credential.model_pattern, [
                  ...new Set(additions),
                ]),
              }
            : credential;
        }),
        protocolConfigs: configs.map((config) => {
          const models = config.models.filter(
            (model) =>
              model.credential_id !== rule?.credentialId ||
              sources.has(protocolConfigModelKey(config, model)),
          );
          for (const item of items) {
            if (
              item.protocol_config_id !== config.id ||
              !config.credential_ids.includes(item.credential_id)
            )
              continue;
            const index = models.findIndex(
              (model) =>
                model.credential_id === item.credential_id &&
                model.model_name === item.model_name,
            );
            if (index >= 0) {
              const existing = models[index];
              if (
                rule &&
                existingSources.has(protocolConfigModelKey(config, existing))
              )
                continue;
              if (!existing.protocols.includes(item.protocol))
                models[index] = {
                  ...existing,
                  protocols: [...existing.protocols, item.protocol],
                };
              continue;
            }
            const member = configs
              .flatMap((entry) => entry.models)
              .find(
                (model) =>
                  model.credential_id === item.credential_id &&
                  model.model_name === item.model_name,
              );
            const model = {
              credential_id: item.credential_id,
              model_name: item.model_name,
              enabled: member?.enabled ?? true,
              protocols: [item.protocol],
              modelIdsByProtocol: {},
              context_window: item.context_window,
              upstream_context_window: null,
            };
            models.push(model);
          }
          return { ...config, models };
        }),
      };
    });

    const contextNames = [
      ...new Set(
        newModels
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
                  const key = protocolConfigModelKey(config, model);
                  const contextWindow = windows[model.model_name];
                  return addedSources.has(key) &&
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

  async function applyModelPattern(
    credentialId: string,
    pattern: string,
    signal: AbortSignal,
  ): Promise<boolean> {
    if (signal.aborted || detectionController.current) return false;
    const trimmed = pattern.trim();
    if (!trimmed) {
      setForm((current) => ({
        ...current,
        credentials: current.credentials.map((credential) =>
          credential.id === credentialId
            ? { ...credential, model_pattern: "" }
            : credential,
        ),
      }));
      return true;
    }
    const rule = { credentialId, pattern: trimmed };
    const catalog = await discoverRemoteCatalog(signal, rule);
    if (!catalog || signal.aborted) return false;
    importRemoteModels(catalog.items, rule);
    return true;
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
    applyModelPattern,
    importRemoteModels,
    detectModelProtocols,
  };
}
