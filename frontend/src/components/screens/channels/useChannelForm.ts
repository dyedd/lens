import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { Site } from "@/lib/api/sites";
import {
  headerDraftsFromJson,
  paramDraftsFromJson,
} from "./channelAdvancedJson";
import { resolveBaseUrlId } from "./channelForm";
import {
  formBaseUrlsForPayload,
  toForm,
  toPayload,
} from "./channelFormConversion";
import {
  aggregateModelGroupKey,
  buildModels,
  createLocalId,
  duplicateProtocolConfigKeys,
  emptyForm,
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

function validateChannelForm(
  form: FormState,
  duplicatedConfigCount: number,
  locale: Locale,
) {
  if (!form.name.trim()) {
    toast.error(locale === "zh-CN" ? "请填写渠道名称" : "Enter a channel name");
    return false;
  }
  if (!form.base_urls.some((item) => item.url.trim())) {
    toast.error(locale === "zh-CN" ? "请填写渠道地址" : "Enter a channel URL");
    return false;
  }
  if (!form.credentials.some((item) => item.api_key.trim())) {
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
          !form.credentials.some(
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
  for (const pattern of [form.model_sync_include, form.model_sync_exclude]) {
    if (!pattern.trim()) continue;
    try {
      new RegExp(pattern.trim());
    } catch {
      toast.error(
        locale === "zh-CN"
          ? `同步筛选正则无效：${pattern.trim()}`
          : `Invalid sync filter regex: ${pattern.trim()}`,
      );
      return false;
    }
  }
  if (invalidProtocolBaseUrlCount(form)) {
    toast.error(
      locale === "zh-CN"
        ? "协议配置地址来源无效"
        : "Protocol config Base URL is invalid",
    );
    return false;
  }
  if (duplicatedConfigCount) {
    toast.error(
      locale === "zh-CN"
        ? "同一个渠道内不允许同一地址重复配置同一种协议"
        : "The same URL cannot expose the same protocol twice",
    );
    return false;
  }
  if (invalidModelProtocolCount(form)) {
    toast.error(
      locale === "zh-CN"
        ? "请为每个模型选择自动透传或指定上游协议"
        : "Choose automatic forwarding or an upstream protocol for every model",
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
  const submittedBaseUrls = useMemo(() => formBaseUrlsForPayload(form), [form]);
  const duplicatedProtocolConfigKeys = useMemo(
    () => duplicateProtocolConfigKeys(form.protocolConfigs, submittedBaseUrls),
    [form.protocolConfigs, submittedBaseUrls],
  );
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
  function confirmDiscardChanges() {
    if (!hasUnsavedChanges) return true;
    return window.confirm(
      locale === "zh-CN"
        ? "当前有未保存修改，确定离开吗？"
        : "You have unsaved changes. Leave anyway?",
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
    if (!confirmDiscardChanges()) return;
    setIsDialogOpen(false);
    setEditingSiteId(null);
  }
  function validateSiteForm() {
    return validateChannelForm(form, duplicatedProtocolConfigKeys.size, locale);
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
    setForm((current) => ({
      ...current,
      base_urls: [
        ...current.base_urls,
        {
          id: createLocalId("baseurl"),
          url: "",
          shareKeys: true,
          newApiKeysLines: "",
        },
      ],
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

  /** Keeps models an upstream stopped listing by handing them to the admin. */
  function keepAggregateModels(keys: string[]) {
    const selected = new Set(keys);
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => ({
        ...config,
        models: config.models.map((model) =>
          selected.has(aggregateModelGroupKey(config, model.model_name))
            ? { ...model, source: "manual", upstream_missing: false }
            : model,
        ),
      })),
    }));
  }
  function addBinding(modelNames: string, protocols: ProtocolKind[]) {
    const names = parseModelNames(modelNames);
    if (!names.length || !protocols.length) return false;
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => {
        const credentialIds = config.credential_ids.length
          ? config.credential_ids
          : current.credentials.map((item) => item.id);
        const newModels = names.flatMap((name) =>
          buildModels(config, credentialIds, name, protocols, "manual"),
        );
        if (!newModels.length) return config;
        return {
          ...config,
          models: [...config.models, ...newModels],
        };
      }),
    }));
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
    confirmDiscardChanges,
    openCreate,
    openEdit,
    closeEditor,
    validateSiteForm,
    hasUnsavedChanges,
    updateModelProtocols,
    removeAggregateModel,
    toggleAggregateEnabled,
    keepAggregateModels,
    addBinding,
    addBaseUrl,
    updateBaseUrl,
    removeBaseUrl,
  };
}
