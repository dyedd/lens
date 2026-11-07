import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { Site } from "@/lib/api/sites";
import {
  headerDraftsFromJson,
  paramDraftsFromJson,
} from "./channelAdvancedJson";
import {
  applyApiKeyDrafts,
  createLocalId,
  emptyForm,
  emptyProtocolConfig,
  invalidModelProtocolCount,
  invalidProtocolBaseUrlCount,
} from "./channelForm";
import {
  endpointSupportsProtocol,
  rebuildProtocolConfigs,
  toForm,
  toPayload,
} from "./channelFormConversion";
import {
  aggregateModelGroupKey,
  protocolConfigModelKey,
} from "./channelModels";
import type { FormBaseUrl, FormState, Locale } from "./channelTypes";

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
  const configs = rebuildProtocolConfigs({ ...form, credentials });
  if (
    credentials.some(
      (credential) =>
        credential.rate_source !== "none" &&
        !configs.some(
          (config) =>
            config.id === credential.rate_protocol_config_id &&
            config.credential_ids.includes(credential.id),
        ),
    )
  ) {
    toast.error(
      locale === "zh-CN"
        ? "请重新选择 Key 的倍率查询地址，或关闭倍率查询"
        : "Choose an allowed rate endpoint or turn off rate lookup",
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
    applyPreparedForm(emptyForm());
    setIsDialogOpen(true);
  }
  function openEdit(site: Site) {
    setEditingSiteId(site.id);
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
      protocolConfigs: current.protocolConfigs.map((config) => ({
        ...config,
        models: config.models.flatMap((model) => {
          if (aggregateModelGroupKey(model.model_name) !== key) return [model];
          const protocols = nextProtocols.filter((protocol) =>
            endpointSupportsProtocol(
              current.base_urls.find((url) => url.id === config.base_url_id)
                ?.kind ?? "default",
              [protocol],
            ),
          );
          return protocols.length ? [{ ...model, protocols }] : [];
        }),
      })),
    }));
  }
  function removeAggregateModel(key: string) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => ({
        ...config,
        models: config.models.filter(
          (model) =>
            aggregateModelGroupKey(model.model_name) !== key &&
            protocolConfigModelKey(config, model) !== key,
        ),
      })),
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
    const removed = form.base_urls[index];
    if (form.base_urls.length <= 1 || !removed) return;
    const removedCount = form.protocolConfigs
      .filter((config) => config.base_url_id === removed.id)
      .reduce(
        (count, config) =>
          count +
          config.models.reduce(
            (total, model) => total + model.protocols.length,
            0,
          ),
        0,
      );
    if (removedCount)
      toast.info(
        locale === "zh-CN"
          ? `保存后将移除 ${removedCount} 个模型出口`
          : `${removedCount} model outlets will be removed on save`,
      );
    setForm((current) => ({
      ...current,
      base_urls: current.base_urls.filter((url) => url.id !== removed.id),
      credentials: current.credentials.map((credential) => ({
        ...credential,
        base_url_ids:
          credential.base_url_ids?.filter((id) => id !== removed.id) ?? null,
      })),
      protocolConfigs: current.protocolConfigs.filter(
        (config) => config.base_url_id !== removed.id,
      ),
    }));
  }

  function toggleAggregateEnabled(key: string, enabled: boolean) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => ({
        ...config,
        models: config.models.map((model) =>
          aggregateModelGroupKey(model.model_name) === key
            ? { ...model, enabled }
            : model,
        ),
      })),
    }));
  }

  /** 同一行的上下文修改覆盖该模型的各把 Key。 */
  function updateModelContextWindow(key: string, contextWindow: number | null) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => ({
        ...config,
        models: config.models.map((model) =>
          aggregateModelGroupKey(model.model_name) === key
            ? { ...model, context_window: contextWindow }
            : model,
        ),
      })),
    }));
  }

  /** Replaces one key's model filter; the next sync reconciles its models. */
  function setCredentialPattern(credentialId: string, pattern: string) {
    setForm((current) => ({
      ...current,
      credentials: current.credentials.map((item) =>
        item.id === credentialId
          ? { ...item, model_pattern: pattern.trim() }
          : item,
      ),
    }));
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
    setCredentialPattern,
    addBaseUrl,
    updateBaseUrl,
    removeBaseUrl,
  };
}
