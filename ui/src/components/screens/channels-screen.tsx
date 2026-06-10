"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { FileInput, Plus } from "lucide-react";
import { toast } from "sonner";
import {
  ApiError,
  ProtocolKind,
  RouteSnapshot,
  Site,
  SiteBatchImportPayload,
  SiteBatchImportResult,
  SiteModelFetchItem,
  SiteModelFetchPayload,
  SiteModelTestPayload,
  SiteModelTestResult,
  SiteRuntimeSummary,
  SettingItem,
  apiRequest,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  MODEL_TEST_PROMPTS_SETTING_KEY,
  parseModelTestPrompts,
} from "@/lib/model-test-prompts";
import { useAppTimeZone } from "@/hooks/use-app-time-zone";
import { DashboardHeaderActions } from "@/components/shell/dashboard-header-actions";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAggregatedModels } from "./channels/model-aggregation";
import { ChannelsOverview } from "./channels/overview";
import {
  activeBaseUrlValue,
  batchImportTemplateText,
  BatchModelTestOption,
  BatchModelTestRow,
  ChannelSort,
  ChannelStatusFilter,
  createLocalId,
  credentialLabel,
  defaultBaseUrlId,
  duplicateProtocolConfigKeys,
  emptyForm,
  emptyProtocolConfig,
  FormBaseUrl,
  FormCredential,
  formBaseUrlsForPayload,
  formHeaders,
  FormProtocolConfig,
  FormState,
  fallbackCredentialName,
  genericModelKey,
  groupPickerModels,
  HeaderItem,
  invalidModelProtocolCount,
  invalidProtocolBaseUrlCount,
  isSiteEnabled,
  ModelTestTarget,
  modelSupportedProtocols,
  nextProtocolConfigName,
  parseBatchImportPayload,
  pickerModelKey,
  pickerModelKeys,
  PickerModelItem,
  protocolConfigDisplayName,
  protocolConfigModelKey,
  resolveBaseUrlId,
  safeText,
  selectedModelTestProtocol,
  siteEndpointSummary,
  siteModelCount,
  SiteRow,
  siteSubtitle,
  toForm,
  toPayload,
  TestableModelOption,
} from "./channels/shared";

const ChannelEditorDialog = dynamic(() =>
  import("./channels/dialogs").then((module) => module.ChannelEditorDialog),
);
const DeleteChannelDialog = dynamic(() =>
  import("./channels/dialogs").then((module) => module.DeleteChannelDialog),
);
const AdvancedProtocolConfigDialog = dynamic(() =>
  import("./channels/form-sections").then(
    (module) => module.AdvancedProtocolConfigDialog,
  ),
);
const BatchImportDialog = dynamic(() =>
  import("./channels/import-dialog").then((module) => module.BatchImportDialog),
);
const BatchModelTestDialog = dynamic(() =>
  import("./channels/model-dialogs").then(
    (module) => module.BatchModelTestDialog,
  ),
);
const ModelTestDialog = dynamic(() =>
  import("./channels/model-dialogs").then((module) => module.ModelTestDialog),
);
const ModelPickerDialog = dynamic(() =>
  import("./channels/model-dialogs").then((module) => module.ModelPickerDialog),
);

export function ChannelsScreen() {
  const queryClient = useQueryClient();
  const { locale } = useI18n();
  const timeZone = useAppTimeZone();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ChannelStatusFilter>("all");
  const [protocolFilter, setProtocolFilter] = useState<"all" | ProtocolKind>(
    "all",
  );
  const [sortBy, setSortBy] = useState<ChannelSort>("requests-desc");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [batchImportOpen, setBatchImportOpen] = useState(false);
  const [batchImportText, setBatchImportText] = useState("");
  const [batchImportError, setBatchImportError] = useState("");
  const [batchImportResult, setBatchImportResult] =
    useState<SiteBatchImportResult | null>(null);
  const [batchImporting, setBatchImporting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Site | null>(null);
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(() => emptyForm(locale));
  const [newProtocolConfigName, setNewProtocolConfigName] = useState("");
  const [protocolConfigNameDialogOpen, setProtocolConfigNameDialogOpen] =
    useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [fetchingProtocolConfigIndex, setFetchingProtocolConfigIndex] =
    useState<number | null>(null);
  const [advancedProtocolConfigIndex, setAdvancedProtocolConfigIndex] =
    useState<number | null>(null);
  const [modelPickerProtocolConfigIndex, setModelPickerProtocolConfigIndex] =
    useState<number | null>(null);
  const [availableModels, setAvailableModels] = useState<PickerModelItem[]>([]);
  const [pickerSelectedModelKeys, setPickerSelectedModelKeys] = useState<
    string[]
  >([]);
  const [modelTestTarget, setModelTestTarget] =
    useState<ModelTestTarget | null>(null);
  const [modelTestPromptMode, setModelTestPromptMode] = useState("0");
  const [modelTestPrompt, setModelTestPrompt] = useState("");
  const [modelTestProtocol, setModelTestProtocol] =
    useState<ProtocolKind | null>(null);
  const [modelTestResult, setModelTestResult] =
    useState<SiteModelTestResult | null>(null);
  const [testingModel, setTestingModel] = useState(false);
  const [batchModelTestOpen, setBatchModelTestOpen] = useState(false);
  const [batchTestingModels, setBatchTestingModels] = useState(false);
  const [batchTestPromptMode, setBatchTestPromptMode] = useState("0");
  const [batchTestConcurrency, setBatchTestConcurrency] = useState("1");
  const [batchTestPrompt, setBatchTestPrompt] = useState("");
  const [batchTestProtocolByKey, setBatchTestProtocolByKey] = useState<
    Record<string, ProtocolKind>
  >({});
  const [batchTestRows, setBatchTestRows] = useState<BatchModelTestRow[]>([]);
  const [formSnapshot, setFormSnapshot] = useState("");

  const {
    data: sites,
    error: sitesError,
    isError: sitesIsError,
    isLoading,
  } = useQuery({
    queryKey: ["sites"],
    queryFn: () => apiRequest<Site[]>("/admin/sites"),
    staleTime: 2 * 60_000,
  });
  const { data: siteRuntimeSummaries } = useQuery({
    queryKey: ["site-runtime-summaries"],
    queryFn: () => apiRequest<SiteRuntimeSummary[]>("/admin/sites/runtime"),
    staleTime: 5_000,
    refetchInterval: 5000,
  });
  const { data: routerSnapshot } = useQuery({
    queryKey: ["router-snapshot"],
    queryFn: () => apiRequest<RouteSnapshot>("/admin/routes"),
    staleTime: 5_000,
    refetchInterval: 5000,
  });
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 5 * 60_000,
  });

  const siteRuntimeById = useMemo(
    () =>
      new Map(
        (siteRuntimeSummaries ?? []).map(
          (item) => [item.site_id, item] as const,
        ),
      ),
    [siteRuntimeSummaries],
  );
  const channelHealthById = useMemo(
    () =>
      new Map(
        (routerSnapshot?.health ?? []).map(
          (item) => [item.channel_id, item] as const,
        ),
      ),
    [routerSnapshot],
  );
  const modelTestPrompts = useMemo(() => {
    const mapping = new Map(
      (settings ?? []).map((item) => [item.key, item.value]),
    );
    return parseModelTestPrompts(mapping.get(MODEL_TEST_PROMPTS_SETTING_KEY));
  }, [settings]);
  const overviewModels = useAggregatedModels(
    form.protocolConfigs,
    form.base_urls,
    locale,
  );
  const modelTestOptionByKey = useMemo(() => {
    const options = new Map<string, TestableModelOption>();
    const credentialById = new Map(
      form.credentials.map(
        (credential, index) => [credential.id, { credential, index }] as const,
      ),
    );
    for (const [
      protocolConfigIndex,
      protocolConfig,
    ] of form.protocolConfigs.entries()) {
      if (
        !protocolConfig.enabled ||
        !activeBaseUrlValue(form, protocolConfig).trim()
      )
        continue;
      for (const [modelIndex, model] of protocolConfig.models.entries()) {
        const key = protocolConfigModelKey(
          protocolConfigIndex,
          protocolConfig,
          model,
        );
        if (options.has(key) || !model.model_name.trim()) continue;
        const credentialEntry = credentialById.get(model.credential_id);
        if (!credentialEntry?.credential.api_key.trim()) continue;
        const protocols = modelSupportedProtocols(model);
        if (!protocols.length) continue;
        options.set(key, {
          key,
          target: { protocolConfigIndex, modelIndex },
          modelName: model.model_name.trim(),
          credentialName: credentialLabel(
            credentialEntry.credential,
            credentialEntry.index,
            locale,
          ),
          protocols,
        });
      }
    }
    return options;
  }, [form, locale]);
  const batchTestOptions = useMemo<BatchModelTestOption[]>(() => {
    const options: BatchModelTestOption[] = [];
    for (const option of modelTestOptionByKey.values()) {
      const selectedProtocol = selectedModelTestProtocol(
        option.protocols,
        batchTestProtocolByKey[option.key] ?? null,
      );
      if (!selectedProtocol) continue;
      options.push({
        ...option,
        selectedProtocol,
      });
    }
    return options;
  }, [batchTestProtocolByKey, modelTestOptionByKey]);
  const siteRows = useMemo<SiteRow[]>(
    () =>
      (sites ?? []).map((site) => ({
        ...site,
        subtitle: siteSubtitle(site),
        enabled_protocol_channel_count: site.protocols.reduce(
          (total, protocolConfig) => {
            if (!protocolConfig.enabled) return total;
            return total + protocolConfig.protocols.length;
          },
          0,
        ),
        model_count: siteModelCount(site),
        endpoint_summary: siteEndpointSummary(site, locale),
      })),
    [sites, locale],
  );
  const visibleSites = useMemo<SiteRow[]>(() => {
    const keyword = search.trim().toLowerCase();
    const filtered = siteRows.filter((site) => {
      if (statusFilter === "enabled" && !isSiteEnabled(site)) return false;
      if (statusFilter === "disabled" && isSiteEnabled(site)) return false;
      if (
        protocolFilter !== "all" &&
        !site.protocols.some((protocolConfig) => {
          if (!protocolConfig.enabled) return false;
          return protocolConfig.protocols.includes(protocolFilter);
        })
      )
        return false;
      if (!keyword) return true;
      const stack = [
        site.name,
        site.subtitle,
        site.endpoint_summary,
        ...site.protocols.flatMap((protocolConfig) =>
          protocolConfig.models.map((model) => model.model_name),
        ),
      ]
        .join(" ")
        .toLowerCase();
      return stack.includes(keyword);
    });

    return [...filtered].sort((left, right) => {
      const leftRequestCount =
        siteRuntimeById.get(left.id)?.recent_request_count ?? 0;
      const rightRequestCount =
        siteRuntimeById.get(right.id)?.recent_request_count ?? 0;
      if (sortBy === "name-asc")
        return left.name.localeCompare(right.name, locale);
      if (sortBy === "name-desc")
        return right.name.localeCompare(left.name, locale);
      if (sortBy === "models-desc")
        return (
          right.model_count - left.model_count ||
          left.name.localeCompare(right.name, locale)
        );
      if (sortBy === "protocols-desc")
        return (
          right.enabled_protocol_channel_count -
            left.enabled_protocol_channel_count ||
          left.name.localeCompare(right.name, locale)
        );
      return (
        rightRequestCount - leftRequestCount ||
        left.name.localeCompare(right.name, locale)
      );
    });
  }, [
    locale,
    protocolFilter,
    search,
    siteRows,
    siteRuntimeById,
    sortBy,
    statusFilter,
  ]);
  const activeFilterCount = [
    Boolean(search.trim()),
    statusFilter !== "all",
    protocolFilter !== "all",
  ].filter(Boolean).length;
  const submittedBaseUrls = useMemo(() => formBaseUrlsForPayload(form), [form]);
  const duplicatedProtocolConfigKeys = useMemo(
    () => duplicateProtocolConfigKeys(form.protocolConfigs, submittedBaseUrls),
    [form.protocolConfigs, submittedBaseUrls],
  );
  const currentSnapshot = useMemo(
    () => JSON.stringify(toPayload(form)),
    [form],
  );
  const hasUnsavedChanges = dialogOpen && currentSnapshot !== formSnapshot;
  useEffect(() => {
    if (!dialogOpen) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dialogOpen, hasUnsavedChanges]);

  useEffect(() => {
    if (!sitesIsError) return;
    toast.error(
      locale === "zh-CN" ? "渠道加载失败" : "Failed to load channels",
      {
        id: "channels-load-error",
        description:
          sitesError instanceof Error
            ? sitesError.message
            : locale === "zh-CN"
              ? "无法读取渠道"
              : "Unable to read channels",
      },
    );
  }, [locale, sitesError, sitesIsError]);

  async function invalidateChannelData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["sites"] }),
      queryClient.invalidateQueries({ queryKey: ["site-runtime-summaries"] }),
      queryClient.invalidateQueries({ queryKey: ["router-snapshot"] }),
      queryClient.invalidateQueries({ queryKey: ["group-candidates"] }),
    ]);
  }

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

  function clearBatchModelTestResults() {
    setBatchModelTestOpen(false);
    setBatchTestPromptMode("0");
    setBatchTestPrompt("");
    setBatchTestProtocolByKey({});
    setBatchTestRows([]);
  }

  function openBatchModelTestDialog() {
    setBatchTestPromptMode("0");
    setBatchTestPrompt(modelTestPrompts[0] || "");
    setBatchTestProtocolByKey({});
    setBatchTestRows([]);
    setBatchModelTestOpen(true);
  }

  function changeBatchTestPromptMode(value: string) {
    setBatchTestPromptMode(value);
    setBatchTestRows([]);
    if (value === "custom") {
      return;
    }
    setBatchTestPrompt(modelTestPrompts[Number(value)] || "");
  }

  function changeBatchTestPrompt(value: string) {
    if (batchTestPromptMode !== "custom") {
      setBatchTestPromptMode("custom");
    }
    setBatchTestPrompt(value);
    setBatchTestRows([]);
  }

  function changeBatchTestProtocol(key: string, protocol: ProtocolKind) {
    setBatchTestProtocolByKey((current) => ({ ...current, [key]: protocol }));
    setBatchTestRows([]);
  }

  function openCreate() {
    if (!confirmDiscardChanges()) return;
    setEditingSiteId(null);
    clearBatchModelTestResults();
    applyPreparedForm(emptyForm(locale));
    setDialogOpen(true);
  }

  function openEdit(site: Site) {
    if (!confirmDiscardChanges()) return;
    setEditingSiteId(site.id);
    clearBatchModelTestResults();
    applyPreparedForm(toForm(site, locale));
    setDialogOpen(true);
  }

  function closeEditor() {
    if (!confirmDiscardChanges()) return;
    setDialogOpen(false);
    setEditingSiteId(null);
  }

  function openBatchImport() {
    setBatchImportText("");
    setBatchImportError("");
    setBatchImportResult(null);
    setBatchImportOpen(true);
  }

  function updateBatchImportText(value: string) {
    setBatchImportText(value);
    setBatchImportError("");
    setBatchImportResult(null);
  }

  async function handleBatchImportFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    try {
      const text = await file.text();
      updateBatchImportText(text);
    } catch (e) {
      const message =
        e instanceof Error
          ? e.message
          : locale === "zh-CN"
            ? "读取文件失败"
            : "Failed to read file";
      setBatchImportError(message);
      setBatchImportResult(null);
    }
  }

  function downloadBatchImportTemplate() {
    const blob = new Blob([batchImportTemplateText()], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "lens-channels-import-template.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function importBatchSites() {
    let payload: SiteBatchImportPayload;
    try {
      payload = parseBatchImportPayload(batchImportText, locale);
    } catch (e) {
      const message =
        e instanceof Error
          ? e.message
          : locale === "zh-CN"
            ? "JSON 格式无效"
            : "Invalid JSON format";
      setBatchImportError(message);
      setBatchImportResult(null);
      return;
    }

    setBatchImporting(true);
    setBatchImportError("");
    try {
      const result = await apiRequest<SiteBatchImportResult>(
        "/admin/sites/import",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );
      setBatchImportResult(result);

      if (result.error_count) {
        toast.error(
          locale === "zh-CN"
            ? "导入校验失败"
            : "Channel import validation failed",
        );
        return;
      }

      if (result.created.length) {
        queryClient.setQueryData<Site[]>(["sites"], (current) => {
          const rows = current ?? [];
          const existingIds = new Set(rows.map((site) => site.id));
          return [
            ...result.created.filter((site) => !existingIds.has(site.id)),
            ...rows,
          ];
        });
        await invalidateChannelData();
        toast.success(
          locale === "zh-CN"
            ? `已导入 ${result.created_count} 个渠道`
            : `Imported ${result.created_count} channels`,
        );
        if (!result.skipped_count) {
          setBatchImportOpen(false);
        }
        return;
      }

      toast.info(
        locale === "zh-CN"
          ? "没有新的渠道被导入"
          : "No new channels were imported",
      );
    } catch (e) {
      const message =
        e instanceof ApiError
          ? e.message
          : locale === "zh-CN"
            ? "导入渠道失败"
            : "Failed to import channels";
      setBatchImportError(message);
      setBatchImportResult(null);
      toast.error(message);
    } finally {
      setBatchImporting(false);
    }
  }

  function resetFilters() {
    setSearch("");
    setStatusFilter("all");
    setProtocolFilter("all");
    setSortBy("requests-desc");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (invalidProtocolBaseUrlCount(form)) {
      toast.error(
        locale === "zh-CN"
          ? "组合地址来源无效"
          : "Combination Base URL is invalid",
      );
      return;
    }
    if (duplicatedProtocolConfigKeys.size) {
      const message =
        locale === "zh-CN"
          ? "同一个渠道内不允许重复地址来源和密钥"
          : "Duplicate Base URL and key pairs are not allowed in one channel";
      toast.error(message);
      return;
    }
    if (invalidModelProtocolCount(form)) {
      toast.error(
        locale === "zh-CN"
          ? "请为每个模型选择至少一个有效协议"
          : "Select at least one valid protocol for every model",
      );
      return;
    }
    try {
      const savedSite = await apiRequest<Site>(
        editingSiteId ? `/admin/sites/${editingSiteId}` : "/admin/sites",
        {
          method: editingSiteId ? "PUT" : "POST",
          body: JSON.stringify(toPayload(form)),
        },
      );
      queryClient.setQueryData<Site[]>(["sites"], (current) => {
        const rows = current ?? [];
        const exists = rows.some((site) => site.id === savedSite.id);
        return exists
          ? rows.map((site) => (site.id === savedSite.id ? savedSite : site))
          : [savedSite, ...rows];
      });
      applyPreparedForm(toForm(savedSite, locale));
      setDialogOpen(false);
      setEditingSiteId(null);
      toast.success(
        editingSiteId
          ? locale === "zh-CN"
            ? "渠道已更新"
            : "Channel updated"
          : locale === "zh-CN"
            ? "渠道已创建"
            : "Channel created",
      );
      await invalidateChannelData();
    } catch (e) {
      const message =
        e instanceof ApiError
          ? e.message
          : locale === "zh-CN"
            ? "保存渠道失败"
            : "Failed to save channel";
      toast.error(message);
    }
  }

  async function removeSite(site: Site) {
    setBusyId(site.id);
    try {
      await apiRequest<void>(`/admin/sites/${site.id}`, { method: "DELETE" });
      queryClient.setQueryData<Site[]>(["sites"], (current) =>
        (current ?? []).filter((item) => item.id !== site.id),
      );
      setDeleteTarget(null);
      if (editingSiteId === site.id) {
        setDialogOpen(false);
        setEditingSiteId(null);
      }
      toast.success(locale === "zh-CN" ? "渠道已删除" : "Channel deleted");
      await invalidateChannelData();
    } catch (e) {
      const message =
        e instanceof ApiError
          ? e.message
          : locale === "zh-CN"
            ? "删除渠道失败"
            : "Failed to delete channel";
      toast.error(message);
    } finally {
      setBusyId(null);
    }
  }

  async function toggleSiteEnabled(site: Site, enabled: boolean) {
    setBusyId(site.id);
    try {
      const updatedSite = await apiRequest<Site>(`/admin/sites/${site.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: site.name,
          base_urls: site.base_urls.map((item) => ({
            id: item.id,
            url: item.url,
            name: item.name,
            enabled: item.enabled,
            supported_protocols: item.supported_protocols ?? [],
          })),
          credentials: site.credentials.map((item) => ({
            id: item.id,
            name: item.name,
            api_key: item.api_key,
            enabled: item.enabled,
          })),
          protocols: site.protocols.map((protocolConfig) => ({
            id: protocolConfig.id,
            name: protocolConfig.name,
            protocols: protocolConfig.protocols,
            enabled,
            headers: protocolConfig.headers,
            channel_proxy: protocolConfig.channel_proxy,
            param_override: protocolConfig.param_override,
            match_regex: protocolConfig.match_regex,
            base_url_id: protocolConfig.base_url_id,
            credential_id: protocolConfig.credential_id,
            models: protocolConfig.models.map((model) => ({
              id: model.id,
              protocol: model.protocol,
              credential_id: model.credential_id,
              model_name: model.model_name,
              enabled: model.enabled,
            })),
          })),
        }),
      });
      queryClient.setQueryData<Site[]>(["sites"], (current) =>
        (current ?? []).map((item) =>
          item.id === updatedSite.id ? updatedSite : item,
        ),
      );
      toast.success(
        enabled
          ? locale === "zh-CN"
            ? "渠道已启用"
            : "Channel enabled"
          : locale === "zh-CN"
            ? "渠道已停用"
            : "Channel disabled",
      );
      await invalidateChannelData();
    } catch (e) {
      const message =
        e instanceof ApiError
          ? e.message
          : locale === "zh-CN"
            ? "更新渠道状态失败"
            : "Failed to update channel status";
      toast.error(message);
    } finally {
      setBusyId(null);
    }
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
      if (current.credentials.length <= 1) {
        return current;
      }
      const target = current.credentials[index];
      if (!target) {
        return current;
      }
      const nextCredentials = current.credentials.filter(
        (_, itemIndex) => itemIndex !== index,
      );
      return {
        ...current,
        credentials: nextCredentials,
        protocolConfigs: current.protocolConfigs.map((protocolConfig) => {
          const credentialId =
            protocolConfig.credential_id === target.id
              ? (nextCredentials[0]?.id ?? "")
              : protocolConfig.credential_id;
          return {
            ...protocolConfig,
            credential_id: credentialId,
            models: protocolConfig.models.filter(
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
      protocolConfigs: current.protocolConfigs.map(
        (protocolConfig, protocolConfigIndex) =>
          protocolConfigIndex === index
            ? { ...protocolConfig, ...patch }
            : protocolConfig,
      ),
    }));
  }

  function updateModelProtocols(
    modelKey: string,
    nextProtocols: ProtocolKind[],
  ) {
    if (nextProtocols.length === 0) {
      toast.error(
        locale === "zh-CN"
          ? "每个模型必须保留至少一个协议"
          : "Each model must retain at least one protocol",
      );
      return;
    }
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map(
        (protocolConfig, protocolConfigIndex) => {
          const modelProtocols = Array.from(new Set(nextProtocols));
          const nextModels = protocolConfig.models.map((model) =>
            protocolConfigModelKey(
              protocolConfigIndex,
              protocolConfig,
              model,
            ) === modelKey
              ? { ...model, protocols: modelProtocols }
              : model,
          );
          return {
            ...protocolConfig,
            models: nextModels,
          };
        },
      ),
    }));
  }

  function openAddProtocolConfigDialog() {
    setNewProtocolConfigName(
      nextProtocolConfigName(form.protocolConfigs, locale),
    );
    setProtocolConfigNameDialogOpen(true);
  }

  function addProtocolConfigWithName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newProtocolConfigName.trim();
    if (!name) {
      toast.error(
        locale === "zh-CN" ? "请输入组合名称" : "Enter a combination name",
      );
      return;
    }
    const exists = form.protocolConfigs.some(
      (protocolConfig, index) =>
        protocolConfigDisplayName(
          protocolConfig,
          index,
          locale,
        ).toLowerCase() === name.toLowerCase(),
    );
    if (exists) {
      toast.error(
        locale === "zh-CN"
          ? "组合名称已存在"
          : "Combination name already exists",
      );
      return;
    }
    setForm((current) => ({
      ...current,
      protocolConfigs: [
        ...current.protocolConfigs,
        {
          ...emptyProtocolConfig(
            defaultBaseUrlId(current.base_urls),
            name,
            current.credentials[0]?.id ?? "",
          ),
        },
      ],
    }));
    setProtocolConfigNameDialogOpen(false);
    setNewProtocolConfigName("");
  }

  function addBaseUrl() {
    const baseUrl = {
      id: createLocalId("baseurl"),
      url: "",
      name: "",
      enabled: true,
      supported_protocols: [] as ProtocolKind[],
    };
    setForm((current) => ({
      ...current,
      base_urls: [...current.base_urls, baseUrl],
    }));
  }

  function updateBaseUrl(index: number, patch: Partial<FormBaseUrl>) {
    setForm((current) => ({
      ...current,
      base_urls: current.base_urls.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  }

  function removeBaseUrl(index: number) {
    setForm((current) => {
      if (current.base_urls.length <= 1) {
        return current;
      }
      const target = current.base_urls[index];
      if (!target) {
        return current;
      }
      const baseUrls = current.base_urls.filter(
        (_, itemIndex) => itemIndex !== index,
      );
      return {
        ...current,
        base_urls: baseUrls,
        protocolConfigs: current.protocolConfigs.map((protocolConfig) => ({
          ...protocolConfig,
          base_url_id: resolveBaseUrlId(baseUrls, protocolConfig.base_url_id),
        })),
      };
    });
  }

  function updateProtocolConfigHeader(
    protocolConfigIndex: number,
    headerIndex: number,
    patch: Partial<HeaderItem>,
  ) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map(
        (protocolConfig, currentProtocolConfigIndex) =>
          currentProtocolConfigIndex !== protocolConfigIndex
            ? protocolConfig
            : {
                ...protocolConfig,
                headers: protocolConfig.headers.map(
                  (header, currentHeaderIndex) =>
                    currentHeaderIndex === headerIndex
                      ? { ...header, ...patch }
                      : header,
                ),
              },
      ),
    }));
  }

  function addManualProtocolConfigModel(
    protocolConfigIndex: number,
    credentialId: string,
  ) {
    const protocolConfig = form.protocolConfigs[protocolConfigIndex];
    const modelName = protocolConfig?.manual_model_name.trim() ?? "";
    if (!protocolConfig || !credentialId || !modelName) return;
    if (
      protocolConfig.models.some(
        (model) =>
          model.credential_id === credentialId &&
          model.model_name === modelName,
      )
    ) {
      toast.info(locale === "zh-CN" ? "模型已存在" : "Model already exists");
      return;
    }
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map(
        (protocolConfig, currentProtocolConfigIndex) => {
          if (currentProtocolConfigIndex !== protocolConfigIndex) {
            return protocolConfig;
          }
          return {
            ...protocolConfig,
            manual_model_name: "",
            expanded: true,
            models: [
              ...protocolConfig.models,
              {
                id: null,
                protocols: [],
                protocolIds: {},
                credential_id: credentialId,
                model_name: modelName,
                enabled: true,
              },
            ],
          };
        },
      ),
    }));
  }

  function togglePickerModel(key: string) {
    setPickerSelectedModelKeys((current) =>
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key],
    );
  }

  function closeModelPicker() {
    setModelPickerProtocolConfigIndex(null);
    setAvailableModels([]);
    setPickerSelectedModelKeys([]);
  }

  function buildModelTestPayload(
    target: ModelTestTarget,
    selectedProtocol: ProtocolKind | null,
    promptValue: string,
  ): SiteModelTestPayload | null {
    const protocolConfig = form.protocolConfigs[target.protocolConfigIndex];
    const model = protocolConfig?.models[target.modelIndex];
    const credentialIndex = model
      ? form.credentials.findIndex((item) => item.id === model.credential_id)
      : -1;
    const credential =
      credentialIndex >= 0 ? form.credentials[credentialIndex] : undefined;
    const activeBaseUrl = protocolConfig
      ? activeBaseUrlValue(form, protocolConfig).trim()
      : "";
    const prompt = promptValue.trim();
    if (
      !protocolConfig ||
      !model ||
      !credential ||
      !credential.api_key.trim() ||
      !activeBaseUrl ||
      !prompt
    ) {
      return null;
    }
    const testProtocol = selectedModelTestProtocol(
      modelSupportedProtocols(model),
      selectedProtocol,
    );
    if (!testProtocol) return null;
    return {
      protocol: testProtocol,
      base_url: activeBaseUrl,
      headers: formHeaders(protocolConfig),
      channel_proxy: protocolConfig.channel_proxy.trim(),
      param_override: protocolConfig.param_override.trim(),
      credential: {
        id: credential.id,
        name: credential.name.trim() || fallbackCredentialName(credentialIndex),
        api_key: credential.api_key.trim(),
      },
      model_name: model.model_name.trim(),
      prompt,
    };
  }

  function openModelTest(protocolConfigIndex: number, modelIndex: number) {
    const protocolConfig = form.protocolConfigs[protocolConfigIndex];
    const model = protocolConfig?.models[modelIndex];
    const protocols = modelSupportedProtocols(model);
    if (!protocols.length) {
      toast.error(
        locale === "zh-CN"
          ? "请先为模型选择有效协议"
          : "Select a valid protocol for the model first",
      );
      return;
    }
    setModelTestTarget({ protocolConfigIndex, modelIndex });
    setModelTestProtocol(protocols[0]);
    setModelTestPromptMode("0");
    setModelTestPrompt(modelTestPrompts[0] || "");
    setModelTestResult(null);
  }

  function openAggregateModelTest(modelKey: string) {
    const option = modelTestOptionByKey.get(modelKey);
    if (!option) {
      toast.error(
        locale === "zh-CN"
          ? "测试参数不完整"
          : "Test parameters are incomplete",
      );
      return;
    }
    const target = option.target;
    openModelTest(target.protocolConfigIndex, target.modelIndex);
  }

  function closeModelTest() {
    if (testingModel) return;
    setModelTestTarget(null);
    setModelTestProtocol(null);
    setModelTestResult(null);
  }

  function changeModelTestPromptMode(value: string) {
    setModelTestPromptMode(value);
    if (value === "custom") {
      return;
    }
    const prompt = modelTestPrompts[Number(value)];
    if (prompt) {
      setModelTestPrompt(prompt);
    }
  }

  function applyModelSelection(selectedKeys: string[]) {
    if (modelPickerProtocolConfigIndex === null) return;
    const selectedModels = availableModels.filter((item) =>
      selectedKeys.includes(pickerModelKey(item)),
    );
    const selectedModelGroups = groupPickerModels(selectedModels);
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map(
        (protocolConfig, protocolConfigIndex) => {
          if (protocolConfigIndex !== modelPickerProtocolConfigIndex) {
            return protocolConfig;
          }
          const merged = [...protocolConfig.models];
          const existingModels = new Map(
            merged.map((model, index) => [genericModelKey(model), index]),
          );
          for (const model of selectedModelGroups) {
            const genericKey = genericModelKey(model);
            const existingIndex = existingModels.get(genericKey);
            if (existingIndex !== undefined) {
              continue;
            }
            existingModels.set(genericKey, merged.length);
            merged.push({
              id: null,
              protocols: [],
              protocolIds: {},
              credential_id: model.credential_id,
              model_name: model.model_name,
              enabled: true,
            });
          }
          return {
            ...protocolConfig,
            models: merged,
            expanded: true,
          };
        },
      ),
    }));
    closeModelPicker();
    if (selectedModelGroups.length) {
      toast.success(
        locale === "zh-CN"
          ? `已加入 ${selectedModelGroups.length} 个模型`
          : `Added ${selectedModelGroups.length} models`,
      );
    }
  }

  async function fetchProtocolModels(protocolConfigIndex: number) {
    const protocolConfig = form.protocolConfigs[protocolConfigIndex];
    if (!protocolConfig) return;
    const selectedCredentialId = protocolConfig.credential_id;
    if (!selectedCredentialId) {
      toast.error(
        locale === "zh-CN" ? "组合密钥无效" : "Combination key is invalid",
      );
      return;
    }
    setFetchingProtocolConfigIndex(protocolConfigIndex);
    try {
      const activeBaseUrl = activeBaseUrlValue(form, protocolConfig);
      const payload: SiteModelFetchPayload = {
        base_url: safeText(activeBaseUrl).trim(),
        headers: formHeaders(protocolConfig),
        channel_proxy: protocolConfig.channel_proxy.trim(),
        match_regex: safeText(protocolConfig.match_regex).trim(),
        credentials: form.credentials
          .map((item, index) => ({
            id: item.id,
            name: item.name.trim() || fallbackCredentialName(index),
            api_key: item.api_key.trim(),
            enabled: item.enabled,
          }))
          .filter((item) => item.api_key),
        credential_id: selectedCredentialId,
      };
      const models = await apiRequest<SiteModelFetchItem[]>(
        "/admin/site-model-discoveries",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );
      const nextAvailableModels = models.map((item) => ({
        credential_id: item.credential_id,
        model_name: item.model_name,
      }));
      setAvailableModels(nextAvailableModels);
      setPickerSelectedModelKeys([]);
      setModelPickerProtocolConfigIndex(protocolConfigIndex);
      toast.success(
        locale === "zh-CN"
          ? `已获取 ${models.length} 个可选模型`
          : `Fetched ${models.length} available models`,
      );
    } catch (e) {
      const message =
        e instanceof ApiError
          ? e.message
          : locale === "zh-CN"
            ? "获取模型失败"
            : "Failed to fetch models";
      toast.error(message);
    } finally {
      setFetchingProtocolConfigIndex(null);
    }
  }

  async function runModelTest() {
    if (!modelTestTarget) return;
    const payload = buildModelTestPayload(
      modelTestTarget,
      modelTestProtocol,
      modelTestPrompt,
    );
    if (!payload) {
      toast.error(
        locale === "zh-CN"
          ? "测试参数不完整"
          : "Test parameters are incomplete",
      );
      return;
    }
    setTestingModel(true);
    setModelTestResult(null);
    try {
      const result = await apiRequest<SiteModelTestResult>(
        "/admin/site-model-tests",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );
      setModelTestResult(result);
      if (result.success) {
        toast.success(
          locale === "zh-CN" ? "模型测试成功" : "Model test succeeded",
        );
      } else {
        toast.error(locale === "zh-CN" ? "模型测试失败" : "Model test failed");
      }
    } catch (e) {
      const message =
        e instanceof ApiError
          ? e.message
          : locale === "zh-CN"
            ? "模型测试失败"
            : "Model test failed";
      setModelTestResult({
        success: false,
        status_code: null,
        latency_ms: 0,
        model_name: payload.model_name,
        credential_id: payload.credential.id,
        output_text: "",
        error_message: message,
      });
      toast.error(message);
    } finally {
      setTestingModel(false);
    }
  }

  function updateBatchTestRow(key: string, patch: Partial<BatchModelTestRow>) {
    setBatchTestRows((current) =>
      current.map((row) => (row.key === key ? { ...row, ...patch } : row)),
    );
  }

  async function runBatchModelTests() {
    const prompt = batchTestPrompt.trim();
    if (!prompt) {
      toast.error(locale === "zh-CN" ? "测试问题为空" : "Test prompt is empty");
      return;
    }
    const entries: Array<{
      key: string;
      payload: SiteModelTestPayload;
      row: BatchModelTestRow;
    }> = [];
    for (const option of batchTestOptions) {
      const payload = buildModelTestPayload(
        option.target,
        option.selectedProtocol,
        prompt,
      );
      if (!payload) continue;
      const key = `${option.key}:${payload.protocol}`;
      entries.push({
        key,
        payload,
        row: {
          key,
          modelName: payload.model_name,
          credentialName: payload.credential.name,
          protocol: payload.protocol,
          status: "pending",
          statusCode: null,
          latencyMs: undefined,
          message: "",
        },
      });
    }
    if (!entries.length) {
      toast.error(
        locale === "zh-CN" ? "没有可测试的模型" : "No testable models",
      );
      return;
    }
    setBatchTestPrompt(prompt);
    setBatchTestRows(entries.map((entry) => entry.row));
    const parsedConcurrency = Number.parseInt(batchTestConcurrency, 10);
    const concurrency = Math.max(
      1,
      Math.min(
        Number.isFinite(parsedConcurrency) ? parsedConcurrency : 1,
        20,
        entries.length,
      ),
    );
    let cursor = 0;
    let succeeded = 0;
    let failed = 0;
    setBatchTestingModels(true);
    try {
      await Promise.all(
        Array.from({ length: concurrency }, async () => {
          while (cursor < entries.length) {
            const entry = entries[cursor];
            cursor += 1;
            updateBatchTestRow(entry.key, {
              status: "running",
              message: "",
            });
            try {
              const result = await apiRequest<SiteModelTestResult>(
                "/admin/site-model-tests",
                {
                  method: "POST",
                  body: JSON.stringify(entry.payload),
                },
              );
              const success = result.success;
              updateBatchTestRow(entry.key, {
                status: success ? "success" : "failed",
                statusCode: result.status_code ?? null,
                latencyMs: result.latency_ms,
                message: success
                  ? result.output_text ||
                    (locale === "zh-CN"
                      ? "上游返回成功，但没有可展示文本"
                      : "Upstream succeeded but returned no displayable text")
                  : result.error_message ||
                    (locale === "zh-CN" ? "测试失败" : "Test failed"),
              });
              if (result.success) {
                succeeded += 1;
              } else {
                failed += 1;
              }
            } catch (error) {
              const message =
                error instanceof Error
                  ? error.message
                  : locale === "zh-CN"
                    ? "测试请求失败"
                    : "Test request failed";
              updateBatchTestRow(entry.key, {
                status: "failed",
                statusCode: null,
                latencyMs: undefined,
                message,
              });
              failed += 1;
            }
          }
        }),
      );
      const message =
        locale === "zh-CN"
          ? `批量测试完成：成功 ${succeeded}，失败 ${failed}`
          : `Batch test finished: ${succeeded} succeeded, ${failed} failed`;
      if (failed) {
        toast.error(message);
      } else {
        toast.success(message);
      }
    } finally {
      setBatchTestingModels(false);
    }
  }

  return (
    <TooltipProvider>
      <DashboardHeaderActions>
        <DropdownMenu>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={locale === "zh-CN" ? "新增渠道" : "Add channels"}
                >
                  <Plus />
                </Button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {locale === "zh-CN" ? "新增渠道" : "Add channels"}
            </TooltipContent>
          </Tooltip>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={openCreate}>
              <Plus />
              {locale === "zh-CN" ? "新建渠道" : "New channel"}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={openBatchImport}>
              <FileInput />
              {locale === "zh-CN" ? "批量导入" : "Import channels"}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </DashboardHeaderActions>
      <section className="flex flex-col gap-4">
        <ChannelsOverview
          locale={locale}
          visibleSites={visibleSites}
          isLoading={isLoading}
          sitesIsError={sitesIsError}
          siteRuntimeById={siteRuntimeById}
          channelHealthById={channelHealthById}
          timeZone={timeZone}
          search={search}
          statusFilter={statusFilter}
          protocolFilter={protocolFilter}
          sortBy={sortBy}
          activeFilterCount={activeFilterCount}
          busyId={busyId}
          onSearchChange={setSearch}
          onStatusChange={setStatusFilter}
          onProtocolChange={setProtocolFilter}
          onSortChange={setSortBy}
          onReset={resetFilters}
          onOpenEdit={openEdit}
          onToggleSiteEnabled={toggleSiteEnabled}
          setDeleteTarget={setDeleteTarget}
        />
        {dialogOpen ? (
          <ChannelEditorDialog
            dialogOpen={dialogOpen}
            hasUnsavedChanges={hasUnsavedChanges}
            editingSiteId={editingSiteId}
            locale={locale}
            form={form}
            newProtocolConfigName={newProtocolConfigName}
            protocolConfigNameDialogOpen={protocolConfigNameDialogOpen}
            fetchingProtocolConfigIndex={fetchingProtocolConfigIndex}
            duplicatedProtocolConfigKeys={duplicatedProtocolConfigKeys}
            batchTestOptions={batchTestOptions}
            batchTestingModels={batchTestingModels}
            testingModel={testingModel}
            overviewModels={overviewModels}
            modelTestOptionByKey={modelTestOptionByKey}
            setDialogOpen={setDialogOpen}
            setEditingSiteId={setEditingSiteId}
            setForm={setForm}
            setNewProtocolConfigName={setNewProtocolConfigName}
            setProtocolConfigNameDialogOpen={setProtocolConfigNameDialogOpen}
            setAdvancedProtocolConfigIndex={setAdvancedProtocolConfigIndex}
            submit={submit}
            addBaseUrl={addBaseUrl}
            updateBaseUrl={updateBaseUrl}
            removeBaseUrl={removeBaseUrl}
            updateCredential={updateCredential}
            removeCredential={removeCredential}
            openAddProtocolConfigDialog={openAddProtocolConfigDialog}
            addProtocolConfigWithName={addProtocolConfigWithName}
            updateProtocolConfig={updateProtocolConfig}
            addManualProtocolConfigModel={addManualProtocolConfigModel}
            fetchProtocolModels={fetchProtocolModels}
            openBatchModelTestDialog={openBatchModelTestDialog}
            updateModelProtocols={updateModelProtocols}
            openAggregateModelTest={openAggregateModelTest}
            closeEditor={closeEditor}
          />
        ) : null}

        {batchImportOpen ? (
          <BatchImportDialog
            open={batchImportOpen}
            onOpenChange={setBatchImportOpen}
            locale={locale}
            importText={batchImportText}
            importError={batchImportError}
            importResult={batchImportResult}
            importing={batchImporting}
            onTextChange={updateBatchImportText}
            onFileChange={(event) => void handleBatchImportFile(event)}
            onDownloadTemplate={downloadBatchImportTemplate}
            onImport={() => void importBatchSites()}
          />
        ) : null}

        {batchModelTestOpen ? (
          <BatchModelTestDialog
            open={batchModelTestOpen}
            locale={locale}
            modelTestPrompts={modelTestPrompts}
            batchTestPromptMode={batchTestPromptMode}
            batchTestPrompt={batchTestPrompt}
            batchTestConcurrency={batchTestConcurrency}
            batchTestOptions={batchTestOptions}
            batchTestRows={batchTestRows}
            batchTestingModels={batchTestingModels}
            onOpenChange={setBatchModelTestOpen}
            onPromptModeChange={changeBatchTestPromptMode}
            onPromptChange={changeBatchTestPrompt}
            onConcurrencyChange={setBatchTestConcurrency}
            onProtocolChange={changeBatchTestProtocol}
            onRun={() => void runBatchModelTests()}
          />
        ) : null}

        {advancedProtocolConfigIndex !== null ? (
          <AdvancedProtocolConfigDialog
            open={advancedProtocolConfigIndex !== null}
            protocolConfig={form.protocolConfigs[advancedProtocolConfigIndex]}
            protocolConfigIndex={advancedProtocolConfigIndex}
            locale={locale}
            onOpenChange={(open) => {
              if (!open) setAdvancedProtocolConfigIndex(null);
            }}
            onUpdateProtocolConfig={updateProtocolConfig}
            onUpdateProtocolConfigHeader={updateProtocolConfigHeader}
          />
        ) : null}

        {deleteTarget ? (
          <DeleteChannelDialog
            deleteTarget={deleteTarget}
            locale={locale}
            busyId={busyId}
            setDeleteTarget={setDeleteTarget}
            removeSite={removeSite}
          />
        ) : null}

        {modelTestTarget ? (
          <ModelTestDialog
            target={modelTestTarget}
            form={form}
            locale={locale}
            modelTestPrompts={modelTestPrompts}
            modelTestPromptMode={modelTestPromptMode}
            modelTestPrompt={modelTestPrompt}
            modelTestProtocol={modelTestProtocol}
            modelTestResult={modelTestResult}
            testingModel={testingModel}
            onClose={closeModelTest}
            onPromptModeChange={changeModelTestPromptMode}
            onPromptChange={(value) => {
              setModelTestPrompt(value);
              if (modelTestPromptMode !== "custom") {
                setModelTestPromptMode("custom");
              }
            }}
            onProtocolChange={setModelTestProtocol}
            onRun={() => void runModelTest()}
          />
        ) : null}

        {modelPickerProtocolConfigIndex !== null ? (
          <ModelPickerDialog
            open={modelPickerProtocolConfigIndex !== null}
            availableModels={availableModels}
            pickerSelectedModelKeys={pickerSelectedModelKeys}
            locale={locale}
            onOpenChange={(open) => {
              if (!open) closeModelPicker();
            }}
            onToggleModel={togglePickerModel}
            onConfirm={() => applyModelSelection(pickerSelectedModelKeys)}
            onConfirmAll={() =>
              applyModelSelection(pickerModelKeys(availableModels))
            }
            onCancel={closeModelPicker}
          />
        ) : null}
      </section>
    </TooltipProvider>
  );
}
