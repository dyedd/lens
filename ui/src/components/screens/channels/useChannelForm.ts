"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { ProtocolKind, Site } from "@/lib/api";
import {
  createLocalId,
  defaultBaseUrlId,
  duplicateProtocolConfigKeys,
  emptyForm,
  emptyProtocolConfig,
  formBaseUrlsForPayload,
  invalidModelProtocolCount,
  invalidProtocolBaseUrlCount,
  nextProtocolConfigName,
  protocolConfigModelKey,
  protocolConfigSelectedCredentialIds,
  resolveBaseUrlId,
  toForm,
  toPayload,
  type FormBaseUrl,
  type FormCredential,
  type FormProtocolConfig,
  type FormState,
  type HeaderItem,
  type Locale,
} from "./channelShared";

function validateChannelForm(
  form: FormState,
  duplicatedConfigCount: number,
  locale: Locale,
) {
  if (invalidProtocolBaseUrlCount(form)) {
    toast.error(
      locale === "zh-CN"
        ? "组合地址来源无效"
        : "Combination Base URL is invalid",
    );
    return false;
  }
  if (duplicatedConfigCount) {
    toast.error(
      locale === "zh-CN"
        ? "同一个渠道内不允许重复地址来源、密钥和协议"
        : "Duplicate Base URL, key, and protocol sets are not allowed in one channel",
    );
    return false;
  }
  if (invalidModelProtocolCount(form)) {
    toast.error(
      locale === "zh-CN"
        ? "请为每个模型选择至少一个有效协议"
        : "Select at least one valid protocol for every model",
    );
    return false;
  }
  return true;
}

/** Protects unsaved edits and focuses a newly added protocol configuration. */
function useChannelFormEffects({
  isDialogOpen,
  hasUnsavedChanges,
  shouldFocusAddedConfig,
  protocolConfigCount,
  finishAddedConfigFocus,
}: {
  isDialogOpen: boolean;
  hasUnsavedChanges: boolean;
  shouldFocusAddedConfig: boolean;
  protocolConfigCount: number;
  finishAddedConfigFocus: () => void;
}) {
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

  useEffect(() => {
    if (!shouldFocusAddedConfig || !isDialogOpen) return;
    const index = protocolConfigCount - 1;
    if (index < 0) return;
    const section = document.querySelector<HTMLElement>(
      `[data-protocol-config-index="${index}"]`,
    );
    if (!section) return;
    section.scrollIntoView({ behavior: "smooth", block: "center" });
    (section.querySelector<HTMLInputElement>("input") ?? section).focus({
      preventScroll: true,
    });
    finishAddedConfigFocus();
  }, [
    finishAddedConfigFocus,
    isDialogOpen,
    protocolConfigCount,
    shouldFocusAddedConfig,
  ]);
}

/** Owns the channel editor form and its local mutations. */
export function useChannelForm(locale: Locale) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(() => emptyForm(locale));
  const [formSnapshot, setFormSnapshot] = useState("");
  const [shouldFocusAddedConfig, setShouldFocusAddedConfig] = useState(false);
  const submittedBaseUrls = useMemo(() => formBaseUrlsForPayload(form), [form]);
  const duplicatedProtocolConfigKeys = useMemo(
    () => duplicateProtocolConfigKeys(form.protocolConfigs, submittedBaseUrls),
    [form.protocolConfigs, submittedBaseUrls],
  );
  const currentSnapshot = useMemo(
    () => JSON.stringify(toPayload(form)),
    [form],
  );
  const hasUnsavedChanges = isDialogOpen && currentSnapshot !== formSnapshot;

  const finishAddedConfigFocus = useCallback(
    () => setShouldFocusAddedConfig(false),
    [],
  );
  useChannelFormEffects({
    isDialogOpen,
    hasUnsavedChanges,
    shouldFocusAddedConfig,
    protocolConfigCount: form.protocolConfigs.length,
    finishAddedConfigFocus,
  });

  function applyPreparedForm(nextForm: FormState) {
    setForm(nextForm);
    setFormSnapshot(JSON.stringify(toPayload(nextForm)));
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
    applyPreparedForm(emptyForm(locale));
    setIsDialogOpen(true);
  }
  function openEdit(site: Site) {
    setEditingSiteId(site.id);
    applyPreparedForm(toForm(site, locale));
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
  function updateCredential(index: number, patch: Partial<FormCredential>) {
    setForm((current) => ({
      ...current,
      credentials: current.credentials.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  }
  function removeCredential(index: number) {
    setForm((current) => {
      if (current.credentials.length <= 1) return current;
      const target = current.credentials[index];
      if (!target) return current;
      const credentials = current.credentials.filter((_, i) => i !== index);
      return {
        ...current,
        credentials,
        protocolConfigs: current.protocolConfigs.map((config) => {
          const ids = protocolConfigSelectedCredentialIds(config).filter(
            (id) => id !== target.id,
          );
          const credentialId = ids.includes(config.credential_id)
            ? config.credential_id
            : (ids[0] ?? credentials[0]?.id ?? "");
          return {
            ...config,
            credential_id: credentialId,
            credential_ids: ids.length
              ? ids
              : credentialId
                ? [credentialId]
                : [],
            models: config.models.filter(
              (model) => model.credential_id !== target.id,
            ),
          };
        }),
      };
    });
  }
  function updateProtocolConfig(
    index: number,
    patch: Partial<FormProtocolConfig>,
  ) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config, i) =>
        i === index ? { ...config, ...patch } : config,
      ),
    }));
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
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config, configIndex) => ({
        ...config,
        models: config.models.map((model) =>
          protocolConfigModelKey(configIndex, config, model) === key
            ? { ...model, protocols: Array.from(new Set(protocols)) }
            : model,
        ),
      })),
    }));
  }
  function removeAggregateModel(key: string) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config, configIndex) => ({
        ...config,
        models: config.models.filter(
          (model) => protocolConfigModelKey(configIndex, config, model) !== key,
        ),
      })),
    }));
  }
  function clearAggregateModels() {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) => ({
        ...config,
        models: [],
      })),
    }));
  }
  function addProtocolConfig() {
    setShouldFocusAddedConfig(true);
    setForm((current) => ({
      ...current,
      protocolConfigs: [
        ...current.protocolConfigs,
        emptyProtocolConfig(
          defaultBaseUrlId(current.base_urls),
          nextProtocolConfigName(current.protocolConfigs, locale),
          current.credentials[0]?.id ?? "",
        ),
      ],
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
          name: "",
          enabled: true,
          supported_protocols: [] as ProtocolKind[],
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
      const baseUrls = current.base_urls.filter((_, i) => i !== index);
      return {
        ...current,
        base_urls: baseUrls,
        protocolConfigs: current.protocolConfigs.map((config) => ({
          ...config,
          base_url_id: resolveBaseUrlId(baseUrls, config.base_url_id),
        })),
      };
    });
  }
  function updateProtocolConfigHeader(
    configIndex: number,
    headerIndex: number,
    patch: Partial<HeaderItem>,
  ) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config, i) =>
        i !== configIndex
          ? config
          : {
              ...config,
              headers: config.headers.map((header, j) =>
                j === headerIndex ? { ...header, ...patch } : header,
              ),
            },
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
    confirmDiscardChanges,
    openCreate,
    openEdit,
    closeEditor,
    validateSiteForm,
    hasUnsavedChanges,
    duplicatedProtocolConfigKeys,
    updateCredential,
    removeCredential,
    updateProtocolConfig,
    updateModelProtocols,
    removeAggregateModel,
    clearAggregateModels,
    addProtocolConfig,
    addBaseUrl,
    updateBaseUrl,
    removeBaseUrl,
    updateProtocolConfigHeader,
  };
}
