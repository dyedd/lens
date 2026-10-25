import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { Site } from "@/lib/api/sites";
import {
  headerDraftsFromJson,
  paramDraftsFromJson,
} from "./channelAdvancedJson";
import { resolveBaseUrlId } from "./channelForm";
import { toForm, toPayload } from "./channelFormConversion";
import {
  aggregateModelGroupKey,
  applyApiKeyDrafts,
  buildModels,
  createLocalId,
  emptyForm,
  emptyProtocolConfig,
  invalidModelProtocolCount,
  invalidProtocolBaseUrlCount,
  isAggregateModelGroupKey,
  protocolConfigModelKey,
} from "./channelModels";
import type { FormBaseUrl, FormState, Locale } from "./channelTypes";

/** Splits pasted model names on commas and line breaks. */
function parseModelNames(value: string) {
  return Array.from(
    new Set(
      value
        .split(/[\n,，]+/)
        .map((name) => name.trim())
        .filter(Boolean),
    ),
  );
}

function validateChannelForm(form: FormState, locale: Locale) {
  const credentials = applyApiKeyDrafts(form).credentials;
  if (!form.name.trim()) {
    toast.error(locale === "zh-CN" ? "请填写渠道名称" : "Enter a channel name");
    return false;
  }
  if (!form.base_urls.some((item) => item.url.trim())) {
    toast.error(locale === "zh-CN" ? "请填写渠道地址" : "Enter a channel URL");
    return false;
  }
  if (!credentials.some((item) => item.api_key.trim())) {
    toast.error(
      locale === "zh-CN"
        ? "请填写至少一个 API Key"
        : "Enter at least one API key",
    );
    return false;
  }
  if (
    form.base_urls
      .slice(1)
      .some(
        (item) =>
          item.url.trim() &&
          item.shareKeys === false &&
          !credentials.some(
            (credential) =>
              credential.baseUrlId === item.id && credential.api_key.trim(),
          ),
      )
  ) {
    toast.error(
      locale === "zh-CN"
        ? "独立密钥的地址至少填写一个 API Key"
        : "Enter at least one API key for URLs that do not share keys",
    );
    return false;
  }
  if (headerDraftsFromJson(form.headersJson) === null) {
    toast.error(
      locale === "zh-CN" ? "请求头 JSON 格式无效" : "Header JSON is invalid",
    );
    return false;
  }
  if (paramDraftsFromJson(form.paramsJson) === null) {
    toast.error(
      locale === "zh-CN" ? "参数 JSON 格式无效" : "Parameter JSON is invalid",
    );
    return false;
  }
  if (invalidProtocolBaseUrlCount(form)) {
    toast.error(
      locale === "zh-CN"
        ? "有地址已留空，该地址下的模型不会被保存；请补全地址或删除该地址"
        : "A base URL is empty, so its models cannot be saved. Fill it in or remove it",
    );
    return false;
  }
  if (invalidModelProtocolCount(form)) {
    toast.error(
      locale === "zh-CN"
        ? "请为每个模型选择上游协议"
        : "Choose an upstream protocol for every model",
    );
    return false;
  }
  return true;
}

/** Warns before closing a tab with unsaved channel edits. */
function useUnsavedChannelGuard(
  isDialogOpen: boolean,
  hasUnsavedChanges: boolean,
) {
  useEffect(() => {
    if (!isDialogOpen) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges, isDialogOpen]);
}

/** Owns the channel editor form and its local mutations. */
export function useChannelForm(locale: Locale) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(() => emptyForm());
  const [formSnapshot, setFormSnapshot] = useState("");
  const [pendingGroupPlacement, setPendingGroupPlacement] = useState<{
    group_id: string;
    model_names: string[];
  } | null>(null);
  const currentSnapshot = useMemo(
    () =>
      JSON.stringify({
        payload: toPayload(form),
        headersJson: form.headersJson,
        paramsJson: form.paramsJson,
      }),
    [form],
  );
  const hasUnsavedChanges = isDialogOpen && currentSnapshot !== formSnapshot;
  useUnsavedChannelGuard(isDialogOpen, hasUnsavedChanges);

  function applyPreparedForm(nextForm: FormState) {
    setForm(nextForm);
    setFormSnapshot(
      JSON.stringify({
        payload: toPayload(nextForm),
        headersJson: nextForm.headersJson,
        paramsJson: nextForm.paramsJson,
      }),
    );
  }
  function openCreate() {
    setEditingSiteId(null);
    setPendingGroupPlacement(null);
    applyPreparedForm(emptyForm());
    setIsDialogOpen(true);
  }
  function openEdit(site: Site) {
    setEditingSiteId(site.id);
    setPendingGroupPlacement(null);
    applyPreparedForm(toForm(site));
    setIsDialogOpen(true);
  }
  function closeEditor() {
    setIsDialogOpen(false);
    setEditingSiteId(null);
  }
  function validateSiteForm() {
    return validateChannelForm(form, locale);
  }
  function updateModelProtocols(key: string, protocols: ProtocolKind[]) {
    if (!protocols.length) {
      toast.error(
        locale === "zh-CN"
          ? "每个模型必须保留至少一个协议"
          : "Each model must retain at least one protocol",
      );
      return;
    }
    const nextProtocols = Array.from(new Set(protocols));
    setForm((current) => ({
      ...current,
      // A collapsed overview row is keyed by model name, so protocol changes
      // cover every credential carrying that model.
      protocolConfigs: current.protocolConfigs.map((config) => ({
        ...config,
        models: config.models.map((model) =>
          aggregateModelGroupKey(config, model.model_name) === key
            ? { ...model, protocols: nextProtocols }
            : model,
        ),
      })),
    }));
  }
  function removeAggregateModel(key: string) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => {
        // Group keys delete every same-name model in this config; per-member
        // keys (from an expanded row) delete just that credential's copy.
        const isGroupKey = isAggregateModelGroupKey(key);
        return {
          ...config,
          models: config.models.filter((model) =>
            isGroupKey
              ? aggregateModelGroupKey(config, model.model_name) !== key
              : protocolConfigModelKey(config, model) !== key,
          ),
        };
      }),
    }));
  }
  function addBaseUrl() {
    const id = createLocalId("baseurl");
    setForm((current) => ({
      ...current,
      base_urls: [
        ...current.base_urls,
        {
          id,
          url: "",
          kind:
            (
              [
                "openai_chat",
                "openai_responses",
                "openai_embedding",
                "openai_image",
                "anthropic",
                "gemini",
                "rerank",
                "models",
                "china",
              ] as const
            ).find(
              (kind) =>
                !current.base_urls.some(
                  (item) =>
                    (item.kind === "default" ? "openai_chat" : item.kind) ===
                    kind,
                ),
            ) ?? "china",
          shareKeys: true,
          newApiKeysLines: "",
        },
      ],
      protocolConfigs: [...current.protocolConfigs, emptyProtocolConfig(id)],
    }));
  }
  function updateBaseUrl(index: number, patch: Partial<FormBaseUrl>) {
    setForm((current) => ({
      ...current,
      base_urls: current.base_urls.map((item, i) =>
        i === index ? { ...item, ...patch } : item,
      ),
    }));
  }
  function removeBaseUrl(index: number) {
    setForm((current) => {
      if (current.base_urls.length <= 1 || !current.base_urls[index])
        return current;
      const removed = current.base_urls[index];
      const baseUrls = current.base_urls.filter((_, i) => i !== index);
      return {
        ...current,
        base_urls: baseUrls,
        credentials: current.credentials.filter(
          (item) => item.baseUrlId !== removed.id,
        ),
        protocolConfigs: current.protocolConfigs.map((config) => ({
          ...config,
          base_url_id: resolveBaseUrlId(baseUrls, config.base_url_id),
        })),
      };
    });
  }
  function toggleAggregateEnabled(key: string, enabled: boolean) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => ({
        ...config,
        models: config.models.map((model) =>
          aggregateModelGroupKey(config, model.model_name) === key
            ? { ...model, enabled }
            : model,
        ),
      })),
    }));
  }

  /** Sets the context window override for every key's copy of a model. */
  function updateModelContextWindow(key: string, contextWindow: number | null) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => ({
        ...config,
        models: config.models.map((model) =>
          aggregateModelGroupKey(config, model.model_name) === key
            ? { ...model, context_window: contextWindow }
            : model,
        ),
      })),
    }));
  }

  function addBinding(
    modelNames: string,
    protocols: ProtocolKind[],
    groupId = "",
  ) {
    const names = parseModelNames(modelNames);
    if (!names.length || !protocols.length) return false;
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => {
        const credentialIds = config.credential_ids.length
          ? config.credential_ids
          : current.credentials.map((item) => item.id);
        const newModels = names.flatMap((name) =>
          buildModels(config, credentialIds, name, protocols),
        );
        if (!newModels.length) return config;
        return {
          ...config,
          models: [...config.models, ...newModels],
        };
      }),
    }));
    if (groupId) {
      setPendingGroupPlacement({ group_id: groupId, model_names: names });
    }
    return true;
  }

  return {
    isDialogOpen,
    setIsDialogOpen,
    editingSiteId,
    setEditingSiteId,
    form,
    setForm,
    applyPreparedForm,
    openCreate,
    openEdit,
    closeEditor,
    validateSiteForm,
    hasUnsavedChanges,
    updateModelProtocols,
    updateModelContextWindow,
    removeAggregateModel,
    toggleAggregateEnabled,
    addBinding,
    pendingGroupPlacement,
    setPendingGroupPlacement,
    addBaseUrl,
    updateBaseUrl,
    removeBaseUrl,
  };
}
