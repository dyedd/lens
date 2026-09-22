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
  syncTargetKey,
} from "./channelModels";
import type {
  FormBaseUrl,
  FormCredential,
  FormModel,
  FormProtocolConfig,
  FormState,
  Locale,
} from "./channelTypes";

function syncTargetsForModel(model: FormModel) {
  return model.protocols.map((protocol) => ({
    credential_id: model.credential_id,
    model_name: model.model_name,
    protocol,
  }));
}

function replaceSyncTargets(
  config: FormProtocolConfig,
  models: FormModel[],
  source: FormModel["source"],
) {
  const nextTargets = models.flatMap(syncTargetsForModel);
  const targetKeys = new Set(nextTargets.map(syncTargetKey));
  const targets = config.sync_targets.filter(
    (target) => !targetKeys.has(syncTargetKey(target)),
  );
  return source === "synced" ? [...targets, ...nextTargets] : targets;
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
  function updateCredential(
    credentialId: string,
    patch: Partial<FormCredential>,
  ) {
    setForm((current) => ({
      ...current,
      credentials: current.credentials.map((item) =>
        item.id === credentialId ? { ...item, ...patch } : item,
      ),
    }));
  }
  function removeCredential(index: number) {
    setForm((current) => {
      const target = current.credentials[index];
      if (!target) return current;
      const credentials = current.credentials.filter((_, i) => i !== index);
      return {
        ...current,
        credentials,
        protocolConfigs: current.protocolConfigs.map((config) => {
          return {
            ...config,
            credential_ids: credentials.map((item) => item.id),
            models: config.models.filter(
              (model) => model.credential_id !== target.id,
            ),
            sync_targets: config.sync_targets.filter(
              (syncTarget) => syncTarget.credential_id !== target.id,
            ),
          };
        }),
      };
    });
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
      protocolConfigs: current.protocolConfigs.map((config) => {
        // A collapsed overview row is keyed by model name, so protocol
        // changes cover every credential carrying that model.
        const selected = config.models.filter(
          (model) => aggregateModelGroupKey(config, model.model_name) === key,
        );
        if (!selected.length) return config;
        return {
          ...config,
          models: config.models.map((model) =>
            aggregateModelGroupKey(config, model.model_name) === key
              ? { ...model, protocols: nextProtocols }
              : model,
          ),
          sync_targets: selected.some((model) => model.source === "synced")
            ? replaceSyncTargets(config, selected, "manual").concat(
                selected.flatMap((model) =>
                  syncTargetsForModel({ ...model, protocols: nextProtocols }),
                ),
              )
            : config.sync_targets,
        };
      }),
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
          sync_targets: config.sync_targets.filter((target) =>
            isGroupKey
              ? aggregateModelGroupKey(config, target.model_name) !== key
              : protocolConfigModelKey(config, {
                  ...target,
                  source: "synced",
                }) !== key,
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
  function addBinding(modelName: string, protocols: ProtocolKind[]) {
    const name = modelName.trim();
    if (!name || !protocols.length) return false;
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => {
        const credentialIds = config.credential_ids.length
          ? config.credential_ids
          : current.credentials.map((item) => item.id);
        const newModels = buildModels(
          config,
          credentialIds,
          name,
          protocols,
          "manual",
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
    updateCredential,
    removeCredential,
    updateModelProtocols,
    removeAggregateModel,
    toggleAggregateEnabled,
    addBinding,
    addBaseUrl,
    updateBaseUrl,
    removeBaseUrl,
  };
}
