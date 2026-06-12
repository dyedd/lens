"use client";

import Image from "next/image";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowDown,
  ArrowUp,
  ImageIcon,
  Palette,
  Plus,
  RotateCcw,
  Save,
  ServerCog,
  ShieldAlert,
  Trash2,
  TestTubeDiagonal,
  UserRound,
  TimerReset,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { Separator } from "@/components/ui/separator";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ApiError,
  type AdminProfile,
  type AdminProfileUpdatePayload,
  type AdminProfileUpdateResponse,
  type SettingItem,
  apiRequest,
} from "@/lib/api";
import { setStoredToken } from "@/lib/auth";
import { useI18n, type Locale } from "@/lib/i18n";
import {
  DEFAULT_MODEL_TEST_PROMPTS,
  MODEL_TEST_PROMPTS_SETTING_KEY,
  parseModelTestPrompts,
  serializeModelTestPrompts,
} from "@/lib/model-test-prompts";
import { cn } from "@/lib/utils";
import { DashboardHeaderActions } from "@/components/shell/dashboard-header-actions";

const PROXY_URL = "proxy_url";
const CORS_ALLOW_ORIGINS = "cors_allow_origins";
const CIRCUIT_BREAKER_THRESHOLD = "circuit_breaker_threshold";
const CIRCUIT_BREAKER_COOLDOWN = "circuit_breaker_cooldown";
const CIRCUIT_BREAKER_MAX_COOLDOWN = "circuit_breaker_max_cooldown";
const HEALTH_WINDOW_SECONDS = "health_window_seconds";
const HEALTH_PENALTY_WEIGHT = "health_penalty_weight";
const HEALTH_MIN_SAMPLES = "health_min_samples";
const RELAY_LOG_BODY_ENABLED = "relay_log_body_enabled";
const MODEL_LIST_COMPAT_MODE_ENABLED = "model_list_compat_mode_enabled";
const UPSTREAM_HEADERS_CONFIG = "upstream_headers_config";
const SITE_NAME = "site_name";
const SITE_LOGO_URL = "site_logo_url";
const TIME_ZONE = "time_zone";

const TIME_ZONE_OPTIONS = [
  { value: "Asia/Shanghai", label: "Asia/Shanghai" },
  { value: "UTC", label: "UTC" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "America/New_York", label: "America/New_York" },
] as const;

type DraftState = {
  proxyUrl: string;
  corsAllowOrigins: string;
  circuitBreakerThreshold: string;
  circuitBreakerCooldown: string;
  circuitBreakerMaxCooldown: string;
  healthWindowSeconds: string;
  healthPenaltyWeight: string;
  healthMinSamples: string;
  relayLogBodyEnabled: boolean;
  modelListCompatModeEnabled: boolean;
  siteName: string;
  siteLogoUrl: string;
  timeZone: string;
  modelTestPrompts: string;
  upstreamHeadersConfig: UpstreamHeadersDraft;
};

type HeaderItem = { key: string; value: string };
type UpstreamHeaderMatchType = "exact" | "regex";
type UpstreamHeaderRuleDraft = {
  id: string;
  enabled: boolean;
  name: string;
  matchType: UpstreamHeaderMatchType;
  models: string;
  pattern: string;
  headers: HeaderItem[];
};
type UpstreamHeadersDraft = {
  global: HeaderItem[];
  rules: UpstreamHeaderRuleDraft[];
};

const EMPTY_HEADERS: HeaderItem[] = [{ key: "", value: "" }];

function createDraftId(prefix: string) {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function emptyUpstreamHeadersDraft(): UpstreamHeadersDraft {
  return { global: [...EMPTY_HEADERS], rules: [] };
}

function emptyUpstreamHeaderRule(): UpstreamHeaderRuleDraft {
  return {
    id: createDraftId("upstream-header-rule"),
    enabled: true,
    name: "",
    matchType: "exact",
    models: "",
    pattern: "",
    headers: [{ key: "", value: "" }],
  };
}

const EMPTY_DRAFT: DraftState = {
  proxyUrl: "",
  corsAllowOrigins: "*",
  circuitBreakerThreshold: "3",
  circuitBreakerCooldown: "60",
  circuitBreakerMaxCooldown: "600",
  healthWindowSeconds: "300",
  healthPenaltyWeight: "0.5",
  healthMinSamples: "10",
  relayLogBodyEnabled: false,
  modelListCompatModeEnabled: false,
  siteName: "Lens",
  siteLogoUrl: "",
  timeZone: "Asia/Shanghai",
  modelTestPrompts: DEFAULT_MODEL_TEST_PROMPTS.join("\n"),
  upstreamHeadersConfig: emptyUpstreamHeadersDraft(),
};

function titleForLocale(locale: Locale, zh: string, en: string) {
  return locale === "zh-CN" ? zh : en;
}

function parseSettings(items: SettingItem[] | undefined) {
  const mapping = new Map((items ?? []).map((item) => [item.key, item.value]));
  return {
    proxyUrl: mapping.get(PROXY_URL) ?? "",
    corsAllowOrigins: mapping.get(CORS_ALLOW_ORIGINS) ?? "*",
    circuitBreakerThreshold: mapping.get(CIRCUIT_BREAKER_THRESHOLD) ?? "3",
    circuitBreakerCooldown: mapping.get(CIRCUIT_BREAKER_COOLDOWN) ?? "60",
    circuitBreakerMaxCooldown:
      mapping.get(CIRCUIT_BREAKER_MAX_COOLDOWN) ?? "600",
    healthWindowSeconds: mapping.get(HEALTH_WINDOW_SECONDS) ?? "300",
    healthPenaltyWeight: mapping.get(HEALTH_PENALTY_WEIGHT) ?? "0.5",
    healthMinSamples: mapping.get(HEALTH_MIN_SAMPLES) ?? "10",
    relayLogBodyEnabled:
      (mapping.get(RELAY_LOG_BODY_ENABLED) ?? "false").trim().toLowerCase() ===
      "true",
    modelListCompatModeEnabled:
      (mapping.get(MODEL_LIST_COMPAT_MODE_ENABLED) ?? "false")
        .trim()
        .toLowerCase() === "true",
    siteName: mapping.get(SITE_NAME) ?? "Lens",
    siteLogoUrl: mapping.get(SITE_LOGO_URL) ?? "",
    timeZone: mapping.get(TIME_ZONE) ?? "Asia/Shanghai",
    modelTestPrompts: parseModelTestPrompts(
      mapping.get(MODEL_TEST_PROMPTS_SETTING_KEY),
    ).join("\n"),
    upstreamHeadersConfig: parseUpstreamHeadersConfig(
      mapping.get(UPSTREAM_HEADERS_CONFIG),
    ),
  } satisfies DraftState;
}

function normalizeOriginList(rawValue: string) {
  const items: string[] = [];
  const seen = new Set<string>();
  for (const chunk of rawValue
    .replace(/\r/g, "\n")
    .replaceAll("，", ",")
    .split("\n")) {
    for (const part of chunk.split(",")) {
      const normalized = part.trim();
      if (!normalized || seen.has(normalized)) {
        continue;
      }
      seen.add(normalized);
      items.push(normalized);
    }
  }
  if (items.includes("*")) {
    return "*";
  }
  return items.join(",");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function parseHeaderRows(value: unknown): HeaderItem[] {
  if (!isRecord(value)) {
    return [{ key: "", value: "" }];
  }
  const rows = Object.entries(value)
    .map(([key, rawValue]) => ({
      key,
      value: typeof rawValue === "string" ? rawValue : String(rawValue ?? ""),
    }))
    .filter((item) => item.key.trim());
  return rows.length ? rows : [{ key: "", value: "" }];
}

function parseModelListText(value: string) {
  const models: string[] = [];
  const seen = new Set<string>();
  for (const item of value.replaceAll("，", ",").split(/[\n,]/)) {
    const model = item.trim();
    if (!model || seen.has(model)) {
      continue;
    }
    seen.add(model);
    models.push(model);
  }
  return models;
}

function headersToRecord(headers: HeaderItem[]) {
  const output: Record<string, string> = {};
  const lowerToKey = new Map<string, string>();
  for (const item of headers) {
    const key = item.key.trim();
    if (!key) {
      continue;
    }
    const lowerKey = key.toLowerCase();
    const existingKey = lowerToKey.get(lowerKey);
    if (existingKey) {
      delete output[existingKey];
    }
    lowerToKey.set(lowerKey, key);
    output[key] = item.value.trim();
  }
  return output;
}

function hasHeaderDraftContent(headers: HeaderItem[]) {
  return headers.some((header) => header.key.trim() || header.value.trim());
}

function hasHeaderValueWithoutKey(headers: HeaderItem[]) {
  return headers.some((header) => header.value.trim() && !header.key.trim());
}

function hasRuleDraftContent(rule: UpstreamHeaderRuleDraft) {
  return Boolean(
    rule.name.trim() ||
    rule.models.trim() ||
    rule.pattern.trim() ||
    hasHeaderDraftContent(rule.headers),
  );
}

function validateUpstreamHeadersConfig(
  config: UpstreamHeadersDraft,
  locale: Locale,
) {
  if (hasHeaderValueWithoutKey(config.global)) {
    return titleForLocale(
      locale,
      "全局请求头名称不能为空。",
      "Global header keys are required.",
    );
  }
  for (const rule of config.rules) {
    if (!hasRuleDraftContent(rule)) {
      continue;
    }
    if (hasHeaderValueWithoutKey(rule.headers)) {
      return titleForLocale(
        locale,
        "规则请求头名称不能为空。",
        "Rule header keys are required.",
      );
    }
    if (!Object.keys(headersToRecord(rule.headers)).length) {
      return titleForLocale(
        locale,
        "模型请求头规则需要至少填写一个请求头名称。",
        "Model header rules need at least one header key.",
      );
    }
    if (rule.matchType === "exact" && !parseModelListText(rule.models).length) {
      return titleForLocale(
        locale,
        "精确匹配规则需要填写至少一个模型名称。",
        "Exact match rules need at least one model name.",
      );
    }
    if (rule.matchType === "regex" && !rule.pattern.trim()) {
      return titleForLocale(
        locale,
        "正则匹配规则需要填写模型正则。",
        "Regex match rules need a model regex.",
      );
    }
  }
  return null;
}

function parseUpstreamHeadersConfig(rawValue: string | undefined) {
  if (!rawValue?.trim()) {
    return emptyUpstreamHeadersDraft();
  }
  try {
    const payload: unknown = JSON.parse(rawValue);
    if (!isRecord(payload)) {
      return emptyUpstreamHeadersDraft();
    }
    const rawRules = Array.isArray(payload["rules"]) ? payload["rules"] : [];
    return {
      global: parseHeaderRows(payload["global"]),
      rules: rawRules.filter(isRecord).map((rule) => {
        const matchType = rule["match_type"] === "regex" ? "regex" : "exact";
        const rawModels = Array.isArray(rule["models"]) ? rule["models"] : [];
        const models = rawModels
          .map((item) => String(item ?? "").trim())
          .filter(Boolean)
          .join("\n");
        return {
          id: createDraftId("upstream-header-rule"),
          enabled: rule["enabled"] !== false,
          name: typeof rule["name"] === "string" ? rule["name"] : "",
          matchType,
          models,
          pattern: typeof rule["pattern"] === "string" ? rule["pattern"] : "",
          headers: parseHeaderRows(rule["headers"]),
        } satisfies UpstreamHeaderRuleDraft;
      }),
    } satisfies UpstreamHeadersDraft;
  } catch {
    return emptyUpstreamHeadersDraft();
  }
}

function serializeUpstreamHeadersConfig(config: UpstreamHeadersDraft) {
  const rules = config.rules.flatMap((rule) => {
    if (!hasRuleDraftContent(rule)) {
      return [];
    }
    const headers = headersToRecord(rule.headers);
    const hasHeaders = Object.keys(headers).length > 0;
    if (!hasHeaders) {
      return [];
    }
    const models = parseModelListText(rule.models);
    const pattern = rule.pattern.trim();
    if (rule.matchType === "exact" && !models.length) {
      return [];
    }
    if (rule.matchType === "regex" && !pattern) {
      return [];
    }
    return [
      {
        enabled: rule.enabled,
        name: rule.name.trim(),
        match_type: rule.matchType,
        models,
        pattern,
        headers,
      },
    ];
  });
  return JSON.stringify({
    global: headersToRecord(config.global),
    rules,
  });
}

function SettingCard({
  title,
  description,
  className,
  children,
}: {
  title: string;
  description?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={cn(
        "min-w-0 rounded-2xl border bg-card px-4 py-4 shadow-sm sm:px-6 sm:py-5",
        className,
      )}
    >
      <header className="border-b pb-4">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        {description ? (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        ) : null}
      </header>
      <div className="flex max-w-2xl flex-col gap-4 pt-5">{children}</div>
    </section>
  );
}

function HeaderRows({
  title,
  headers,
  locale,
  onAdd,
  onUpdate,
  onRemove,
}: {
  title: string;
  headers: HeaderItem[];
  locale: Locale;
  onAdd: () => void;
  onUpdate: (index: number, patch: Partial<HeaderItem>) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          <Plus data-icon="inline-start" />
          {titleForLocale(locale, "添加", "Add")}
        </Button>
      </div>
      {headers.map((header, headerIndex) => (
        <div
          key={headerIndex}
          className="grid gap-3 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
        >
          <Field>
            <FieldLabel>
              {titleForLocale(locale, "请求头名称", "Header key")}
            </FieldLabel>
            <Input
              value={header.key}
              onChange={(event) =>
                onUpdate(headerIndex, { key: event.target.value })
              }
              placeholder="X-Header-Name"
            />
          </Field>
          <Field>
            <FieldLabel>
              {titleForLocale(locale, "请求头值", "Header value")}
            </FieldLabel>
            <Input
              value={header.value}
              onChange={(event) =>
                onUpdate(headerIndex, { value: event.target.value })
              }
              placeholder="value"
            />
          </Field>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="text-muted-foreground"
            aria-label={titleForLocale(locale, "删除请求头", "Remove header")}
            onClick={() => onRemove(headerIndex)}
          >
            <Trash2 data-icon="inline-start" />
          </Button>
        </div>
      ))}
    </div>
  );
}

export function SettingsScreen() {
  const queryClient = useQueryClient();
  const { locale, setLocale } = useI18n();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 5 * 60_000,
  });
  const { data: profile } = useQuery({
    queryKey: ["auth-me"],
    queryFn: () => apiRequest<AdminProfile>("/admin/session"),
    staleTime: 5 * 60_000,
  });

  const [draft, setDraft] = useState<DraftState>(EMPTY_DRAFT);
  const [accountForm, setAccountForm] = useState({
    username: "admin",
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [saving, setSaving] = useState(false);
  const [updatingAccount, setUpdatingAccount] = useState(false);

  useEffect(() => {
    if (settingsQuery.isSuccess) {
      setDraft(parseSettings(settingsQuery.data));
    }
  }, [settingsQuery.data, settingsQuery.isSuccess]);

  useEffect(() => {
    setAccountForm((current) => ({
      ...current,
      username: profile?.username || "admin",
    }));
  }, [profile?.username]);

  useEffect(() => {
    if (!settingsQuery.isError) return;
    toast.error(
      titleForLocale(locale, "设置加载失败", "Failed to load settings"),
      {
        id: "settings-load-error",
        description:
          settingsQuery.error instanceof Error
            ? settingsQuery.error.message
            : titleForLocale(
                locale,
                "无法读取系统设置",
                "Unable to read system settings",
              ),
      },
    );
  }, [locale, settingsQuery.error, settingsQuery.isError]);

  function setDraftValue<K extends keyof DraftState>(
    key: K,
    value: DraftState[K],
  ) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function updateUpstreamHeadersConfig(
    updater: (current: UpstreamHeadersDraft) => UpstreamHeadersDraft,
  ) {
    setDraft((current) => ({
      ...current,
      upstreamHeadersConfig: updater(current.upstreamHeadersConfig),
    }));
  }

  function updateGlobalHeader(index: number, patch: Partial<HeaderItem>) {
    updateUpstreamHeadersConfig((current) => ({
      ...current,
      global: current.global.map((header, currentIndex) =>
        currentIndex === index ? { ...header, ...patch } : header,
      ),
    }));
  }

  function removeGlobalHeader(index: number) {
    updateUpstreamHeadersConfig((current) => {
      const nextHeaders = current.global.filter(
        (_, currentIndex) => currentIndex !== index,
      );
      return {
        ...current,
        global: nextHeaders.length ? nextHeaders : [{ key: "", value: "" }],
      };
    });
  }

  function updateUpstreamHeaderRule(
    index: number,
    patch: Partial<UpstreamHeaderRuleDraft>,
  ) {
    updateUpstreamHeadersConfig((current) => ({
      ...current,
      rules: current.rules.map((rule, currentIndex) =>
        currentIndex === index ? { ...rule, ...patch } : rule,
      ),
    }));
  }

  function removeUpstreamHeaderRule(index: number) {
    updateUpstreamHeadersConfig((current) => ({
      ...current,
      rules: current.rules.filter((_, currentIndex) => currentIndex !== index),
    }));
  }

  function moveUpstreamHeaderRule(index: number, direction: -1 | 1) {
    updateUpstreamHeadersConfig((current) => {
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= current.rules.length) {
        return current;
      }
      const rules = [...current.rules];
      const rule = rules[index];
      if (!rule) {
        return current;
      }
      rules.splice(index, 1);
      rules.splice(nextIndex, 0, rule);
      return { ...current, rules };
    });
  }

  function updateRuleHeader(
    ruleIndex: number,
    headerIndex: number,
    patch: Partial<HeaderItem>,
  ) {
    updateUpstreamHeadersConfig((current) => ({
      ...current,
      rules: current.rules.map((rule, currentRuleIndex) =>
        currentRuleIndex === ruleIndex
          ? {
              ...rule,
              headers: rule.headers.map((header, currentHeaderIndex) =>
                currentHeaderIndex === headerIndex
                  ? { ...header, ...patch }
                  : header,
              ),
            }
          : rule,
      ),
    }));
  }

  function removeRuleHeader(ruleIndex: number, headerIndex: number) {
    updateUpstreamHeadersConfig((current) => ({
      ...current,
      rules: current.rules.map((rule, currentRuleIndex) => {
        if (currentRuleIndex !== ruleIndex) {
          return rule;
        }
        const nextHeaders = rule.headers.filter(
          (_, currentHeaderIndex) => currentHeaderIndex !== headerIndex,
        );
        return {
          ...rule,
          headers: nextHeaders.length ? nextHeaders : [{ key: "", value: "" }],
        };
      }),
    }));
  }

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["settings"] }),
      queryClient.invalidateQueries({ queryKey: ["public-branding"] }),
      queryClient.invalidateQueries({ queryKey: ["app-info"] }),
      queryClient.invalidateQueries({ queryKey: ["model-groups"] }),
      queryClient.invalidateQueries({ queryKey: ["overview-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["overview-daily"] }),
      queryClient.invalidateQueries({ queryKey: ["overview-models"] }),
    ]);
  }

  async function submitSettings() {
    if (!settingsQuery.isSuccess) {
      return;
    }
    const upstreamHeadersError = validateUpstreamHeadersConfig(
      draft.upstreamHeadersConfig,
      locale,
    );
    if (upstreamHeadersError) {
      toast.error(upstreamHeadersError);
      return;
    }
    setSaving(true);
    try {
      const items: SettingItem[] = [
        { key: PROXY_URL, value: draft.proxyUrl.trim() },
        {
          key: CORS_ALLOW_ORIGINS,
          value: normalizeOriginList(draft.corsAllowOrigins) || "*",
        },
        {
          key: CIRCUIT_BREAKER_THRESHOLD,
          value: draft.circuitBreakerThreshold.trim() || "3",
        },
        {
          key: CIRCUIT_BREAKER_COOLDOWN,
          value: draft.circuitBreakerCooldown.trim() || "60",
        },
        {
          key: CIRCUIT_BREAKER_MAX_COOLDOWN,
          value: draft.circuitBreakerMaxCooldown.trim() || "600",
        },
        {
          key: HEALTH_WINDOW_SECONDS,
          value: draft.healthWindowSeconds.trim() || "300",
        },
        {
          key: HEALTH_PENALTY_WEIGHT,
          value: draft.healthPenaltyWeight.trim() || "0.5",
        },
        {
          key: HEALTH_MIN_SAMPLES,
          value: draft.healthMinSamples.trim() || "10",
        },
        {
          key: RELAY_LOG_BODY_ENABLED,
          value: draft.relayLogBodyEnabled ? "true" : "false",
        },
        {
          key: MODEL_LIST_COMPAT_MODE_ENABLED,
          value: draft.modelListCompatModeEnabled ? "true" : "false",
        },
        { key: SITE_NAME, value: draft.siteName.trim() || "Lens" },
        { key: SITE_LOGO_URL, value: draft.siteLogoUrl.trim() },
        { key: TIME_ZONE, value: draft.timeZone.trim() || "Asia/Shanghai" },
        {
          key: MODEL_TEST_PROMPTS_SETTING_KEY,
          value: serializeModelTestPrompts(draft.modelTestPrompts),
        },
        {
          key: UPSTREAM_HEADERS_CONFIG,
          value: serializeUpstreamHeadersConfig(draft.upstreamHeadersConfig),
        },
      ];
      await apiRequest<SettingItem[]>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ items }),
      });
      toast.success(titleForLocale(locale, "设置已保存", "Settings saved"));
      await refresh();
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(locale, "保存设置失败", "Failed to save settings");
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  async function submitAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextUsername = accountForm.username.trim();
    const wantsPasswordUpdate = Boolean(
      accountForm.currentPassword ||
      accountForm.newPassword ||
      accountForm.confirmPassword,
    );
    const usernameChanged = nextUsername !== (profile?.username || "admin");

    if (!nextUsername) {
      toast.error(
        titleForLocale(locale, "用户名不能为空", "Username is required"),
      );
      return;
    }

    if (!usernameChanged && !wantsPasswordUpdate) {
      toast.success(
        titleForLocale(
          locale,
          "没有需要保存的账号变更",
          "No account changes to save",
        ),
      );
      return;
    }

    if (
      wantsPasswordUpdate &&
      (!accountForm.currentPassword || !accountForm.newPassword)
    ) {
      toast.error(
        titleForLocale(
          locale,
          "请填写完整密码",
          "Please fill in both passwords",
        ),
      );
      return;
    }

    if (accountForm.newPassword !== accountForm.confirmPassword) {
      toast.error(
        titleForLocale(
          locale,
          "两次新密码不一致",
          "The new passwords do not match",
        ),
      );
      return;
    }

    const payload: AdminProfileUpdatePayload = {
      username: nextUsername,
      current_password: accountForm.currentPassword,
      new_password: accountForm.newPassword,
    };
    setUpdatingAccount(true);
    try {
      const response = await apiRequest<AdminProfileUpdateResponse>(
        "/admin/profile",
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
      );
      setStoredToken(response.access_token);
      window.sessionStorage.removeItem("lens_admin_profile_cache");
      queryClient.setQueryData(["auth-me"], response.profile);
      await queryClient.invalidateQueries({ queryKey: ["auth-me"] });
      toast.success(titleForLocale(locale, "账号已更新", "Account updated"));
      setAccountForm({
        username: response.profile.username,
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
      });
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(locale, "更新账号失败", "Failed to update account");
      toast.error(message);
    } finally {
      setUpdatingAccount(false);
    }
  }

  const refreshLabel = titleForLocale(locale, "刷新", "Refresh");
  const saveSettingsLabel = saving
    ? titleForLocale(locale, "保存中...", "Saving...")
    : titleForLocale(locale, "保存设置", "Save settings");
  const settingsTabs = [
    {
      value: "appearance",
      label: titleForLocale(locale, "站点外观", "Appearance"),
      description: titleForLocale(
        locale,
        "站点名称、Logo 和默认语言。",
        "Site name, logo, and default language.",
      ),
      icon: Palette,
    },
    {
      value: "account",
      label: titleForLocale(locale, "账号", "Account"),
      description: titleForLocale(
        locale,
        "管理员用户名和登录密码。",
        "Admin username and sign-in password.",
      ),
      icon: UserRound,
    },
    {
      value: "time",
      label: titleForLocale(locale, "时间", "Time"),
      description: titleForLocale(
        locale,
        "系统显示和统计使用的时区。",
        "Time zone used by display and statistics.",
      ),
      icon: TimerReset,
    },
    {
      value: "gateway",
      label: titleForLocale(locale, "网关", "Gateway"),
      description: titleForLocale(
        locale,
        "代理、跨域、日志和上游请求设置。",
        "Proxy, CORS, logs, and upstream request settings.",
      ),
      icon: ServerCog,
    },
    {
      value: "model-test",
      label: titleForLocale(locale, "模型测试", "Model test"),
      description: titleForLocale(
        locale,
        "批量测试模型时使用的预设问题。",
        "Preset prompts used when testing models.",
      ),
      icon: TestTubeDiagonal,
    },
    {
      value: "circuit-breaker",
      label: titleForLocale(locale, "熔断器", "Circuit breaker"),
      description: titleForLocale(
        locale,
        "失败阈值、冷却时间和健康评分参数。",
        "Failure threshold, cooldown, and health scoring parameters.",
      ),
      icon: ShieldAlert,
    },
  ] as const;

  return (
    <>
      <DashboardHeaderActions>
        <div className="flex items-center justify-end gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                type="button"
                aria-label={refreshLabel}
                onClick={() => void refresh()}
              >
                <RotateCcw data-icon="inline-start" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {refreshLabel}
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={saveSettingsLabel}
                disabled={saving || !settingsQuery.isSuccess}
                onClick={() => void submitSettings()}
              >
                <Save data-icon="inline-start" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {saveSettingsLabel}
            </TooltipContent>
          </Tooltip>
        </div>
      </DashboardHeaderActions>

      <section className="min-w-0">
        <Tabs
          defaultValue="appearance"
          orientation="vertical"
          className="grid min-w-0 gap-6 lg:grid-cols-[220px_minmax(0,760px)] lg:items-start"
        >
          <TabsList className="flex h-auto w-full flex-row justify-start gap-1 overflow-x-auto rounded-none bg-transparent p-0 text-foreground lg:sticky lg:top-4 lg:flex-col lg:items-start lg:overflow-visible">
            {settingsTabs.map((item) => {
              const Icon = item.icon;
              return (
                <TabsTrigger
                  key={item.value}
                  value={item.value}
                  className="h-9 w-40 shrink-0 justify-start gap-2 rounded-md px-3 text-sm data-[state=active]:bg-sidebar-accent data-[state=active]:shadow-none"
                >
                  <Icon className="size-4" />
                  <span>{item.label}</span>
                </TabsTrigger>
              );
            })}
          </TabsList>

          <div className="min-w-0">
            <TabsContent value="appearance" className="mt-0">
              <SettingCard
                title={titleForLocale(locale, "站点外观", "Appearance")}
                description={settingsTabs[0].description}
              >
                <FieldGroup>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "语言", "Language")}
                    </FieldLabel>
                    <SegmentedControl
                      className="!w-fit self-start"
                      value={locale}
                      onValueChange={(value) => setLocale(value)}
                      options={[
                        { value: "zh-CN", label: "简体中文" },
                        { value: "en-US", label: "English" },
                      ]}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "站点名称", "Site name")}
                    </FieldLabel>
                    <Input
                      value={draft.siteName}
                      onChange={(event) =>
                        setDraftValue("siteName", event.target.value)
                      }
                      placeholder="Lens"
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "Logo 地址", "Logo URL")}
                    </FieldLabel>
                    <Input
                      value={draft.siteLogoUrl}
                      onChange={(event) =>
                        setDraftValue("siteLogoUrl", event.target.value)
                      }
                      placeholder="https://example.com/logo.svg"
                    />
                  </Field>
                </FieldGroup>
                <div className="flex items-center gap-3 rounded-md border bg-muted/40 px-4 py-3">
                  <span className="flex size-12 items-center justify-center overflow-hidden rounded-md border bg-background">
                    {draft.siteLogoUrl.trim() ? (
                      <Image
                        src={draft.siteLogoUrl.trim()}
                        alt={draft.siteName || "logo"}
                        width={48}
                        height={48}
                        className="size-12 object-contain"
                        unoptimized
                      />
                    ) : (
                      <ImageIcon className="text-muted-foreground" />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-foreground">
                      {draft.siteName.trim() || "Lens"}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {draft.siteLogoUrl.trim() ||
                        titleForLocale(
                          locale,
                          "未设置 Logo",
                          "No logo configured",
                        )}
                    </div>
                  </div>
                </div>
              </SettingCard>
            </TabsContent>

            <TabsContent value="account" className="mt-0">
              <SettingCard
                title={titleForLocale(locale, "账号", "Account")}
                description={settingsTabs[1].description}
              >
                <form className="flex flex-col gap-4" onSubmit={submitAccount}>
                  <FieldGroup>
                    <Field>
                      <FieldLabel>
                        {titleForLocale(locale, "用户名", "Username")}
                      </FieldLabel>
                      <Input
                        value={accountForm.username}
                        onChange={(event) =>
                          setAccountForm((current) => ({
                            ...current,
                            username: event.target.value,
                          }))
                        }
                        autoComplete="username"
                      />
                    </Field>
                    <Field>
                      <FieldLabel>
                        {titleForLocale(locale, "当前密码", "Current password")}
                      </FieldLabel>
                      <Input
                        type="password"
                        value={accountForm.currentPassword}
                        onChange={(event) =>
                          setAccountForm((current) => ({
                            ...current,
                            currentPassword: event.target.value,
                          }))
                        }
                        autoComplete="current-password"
                      />
                    </Field>
                    <Field>
                      <FieldLabel>
                        {titleForLocale(locale, "新密码", "New password")}
                      </FieldLabel>
                      <Input
                        type="password"
                        value={accountForm.newPassword}
                        onChange={(event) =>
                          setAccountForm((current) => ({
                            ...current,
                            newPassword: event.target.value,
                          }))
                        }
                        autoComplete="new-password"
                      />
                    </Field>
                    <Field>
                      <FieldLabel>
                        {titleForLocale(
                          locale,
                          "确认新密码",
                          "Confirm new password",
                        )}
                      </FieldLabel>
                      <Input
                        type="password"
                        value={accountForm.confirmPassword}
                        onChange={(event) =>
                          setAccountForm((current) => ({
                            ...current,
                            confirmPassword: event.target.value,
                          }))
                        }
                        autoComplete="new-password"
                      />
                    </Field>
                  </FieldGroup>
                  <Button
                    type="submit"
                    variant="outline"
                    disabled={updatingAccount}
                  >
                    {updatingAccount
                      ? titleForLocale(locale, "提交中...", "Updating...")
                      : titleForLocale(locale, "保存账号", "Save account")}
                  </Button>
                </form>
              </SettingCard>
            </TabsContent>

            <TabsContent value="time" className="mt-0">
              <SettingCard
                title={titleForLocale(locale, "时间", "Time")}
                description={settingsTabs[2].description}
              >
                <FieldGroup>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "时区", "Time zone")}
                    </FieldLabel>
                    <NativeSelect
                      className="w-full"
                      value={draft.timeZone || "Asia/Shanghai"}
                      onChange={(event) =>
                        setDraftValue("timeZone", event.target.value)
                      }
                    >
                      {TIME_ZONE_OPTIONS.map((option) => (
                        <NativeSelectOption
                          key={option.value}
                          value={option.value}
                        >
                          {option.label}
                        </NativeSelectOption>
                      ))}
                    </NativeSelect>
                  </Field>
                </FieldGroup>
              </SettingCard>
            </TabsContent>

            <TabsContent value="gateway" className="mt-0">
              <SettingCard
                title={titleForLocale(locale, "网关", "Gateway")}
                description={settingsTabs[3].description}
              >
                <FieldGroup>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(
                        locale,
                        "全局代理地址",
                        "Global proxy URL",
                      )}
                    </FieldLabel>
                    <Input
                      value={draft.proxyUrl}
                      onChange={(event) =>
                        setDraftValue("proxyUrl", event.target.value)
                      }
                      placeholder="http://127.0.0.1:7890"
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(
                        locale,
                        "CORS 跨域名单",
                        "CORS allow origins",
                      )}
                    </FieldLabel>
                    <Textarea
                      className="min-h-[92px]"
                      value={draft.corsAllowOrigins}
                      onChange={(event) =>
                        setDraftValue("corsAllowOrigins", event.target.value)
                      }
                      placeholder={"*\nhttp://localhost:3000"}
                    />
                  </Field>
                  <Field
                    orientation="horizontal"
                    className="items-center justify-between gap-4"
                  >
                    <FieldContent>
                      <FieldLabel className="w-auto">
                        {titleForLocale(
                          locale,
                          "模型列表兼容模式",
                          "Model list compatibility mode",
                        )}
                      </FieldLabel>
                      <FieldDescription>
                        {titleForLocale(
                          locale,
                          "开启后 /v1/models 会以 OpenAI 格式列出全部协议模型；如果客户端不支持某协议，实际请求仍可能失败。",
                          "When enabled, /v1/models lists all protocol models in OpenAI format; requests can still fail if the client cannot call a protocol.",
                        )}
                      </FieldDescription>
                    </FieldContent>
                    <Switch
                      checked={draft.modelListCompatModeEnabled}
                      onCheckedChange={(checked) =>
                        setDraftValue("modelListCompatModeEnabled", checked)
                      }
                    />
                  </Field>
                  <Field
                    orientation="horizontal"
                    className="items-center justify-between gap-4"
                  >
                    <FieldContent>
                      <FieldLabel className="w-auto">
                        {titleForLocale(
                          locale,
                          "记录日志正文",
                          "Record log body",
                        )}
                      </FieldLabel>
                    </FieldContent>
                    <Switch
                      checked={draft.relayLogBodyEnabled}
                      onCheckedChange={(checked) =>
                        setDraftValue("relayLogBodyEnabled", checked)
                      }
                    />
                  </Field>
                  <div className="flex flex-col gap-5 rounded-lg border bg-muted/20 p-4">
                    <HeaderRows
                      title={titleForLocale(
                        locale,
                        "全局请求头",
                        "Global headers",
                      )}
                      headers={draft.upstreamHeadersConfig.global}
                      locale={locale}
                      onAdd={() =>
                        updateUpstreamHeadersConfig((current) => ({
                          ...current,
                          global: [...current.global, { key: "", value: "" }],
                        }))
                      }
                      onUpdate={updateGlobalHeader}
                      onRemove={removeGlobalHeader}
                    />
                    <Separator />
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-foreground">
                        {titleForLocale(
                          locale,
                          "模型请求头规则",
                          "Model header rules",
                        )}
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          updateUpstreamHeadersConfig((current) => ({
                            ...current,
                            rules: [
                              ...current.rules,
                              emptyUpstreamHeaderRule(),
                            ],
                          }))
                        }
                      >
                        <Plus data-icon="inline-start" />
                        {titleForLocale(locale, "添加规则", "Add rule")}
                      </Button>
                    </div>
                    {draft.upstreamHeadersConfig.rules.length ? (
                      <div className="flex flex-col gap-4">
                        {draft.upstreamHeadersConfig.rules.map(
                          (rule, ruleIndex) => (
                            <div
                              key={rule.id}
                              className="flex flex-col gap-4 rounded-lg border bg-background p-3"
                            >
                              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-end">
                                <Field>
                                  <FieldLabel>
                                    {titleForLocale(
                                      locale,
                                      "规则名称",
                                      "Rule name",
                                    )}
                                  </FieldLabel>
                                  <Input
                                    value={rule.name}
                                    onChange={(event) =>
                                      updateUpstreamHeaderRule(ruleIndex, {
                                        name: event.target.value,
                                      })
                                    }
                                    placeholder={titleForLocale(
                                      locale,
                                      "规则名称",
                                      "Rule name",
                                    )}
                                  />
                                </Field>
                                <Field>
                                  <FieldLabel>
                                    {titleForLocale(
                                      locale,
                                      "匹配方式",
                                      "Match type",
                                    )}
                                  </FieldLabel>
                                  <SegmentedControl<UpstreamHeaderMatchType>
                                    value={rule.matchType}
                                    onValueChange={(matchType) =>
                                      updateUpstreamHeaderRule(ruleIndex, {
                                        matchType,
                                      })
                                    }
                                    options={[
                                      {
                                        value: "exact",
                                        label: titleForLocale(
                                          locale,
                                          "精确",
                                          "Exact",
                                        ),
                                      },
                                      {
                                        value: "regex",
                                        label: titleForLocale(
                                          locale,
                                          "正则",
                                          "Regex",
                                        ),
                                      },
                                    ]}
                                  />
                                </Field>
                                <div className="flex items-center justify-between gap-2 lg:justify-end">
                                  <Switch
                                    checked={rule.enabled}
                                    aria-label={titleForLocale(
                                      locale,
                                      "启用规则",
                                      "Enable rule",
                                    )}
                                    onCheckedChange={(enabled) =>
                                      updateUpstreamHeaderRule(ruleIndex, {
                                        enabled,
                                      })
                                    }
                                  />
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="icon"
                                    aria-label={titleForLocale(
                                      locale,
                                      "上移规则",
                                      "Move rule up",
                                    )}
                                    disabled={ruleIndex === 0}
                                    onClick={() =>
                                      moveUpstreamHeaderRule(ruleIndex, -1)
                                    }
                                  >
                                    <ArrowUp data-icon="inline-start" />
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="icon"
                                    aria-label={titleForLocale(
                                      locale,
                                      "下移规则",
                                      "Move rule down",
                                    )}
                                    disabled={
                                      ruleIndex ===
                                      draft.upstreamHeadersConfig.rules.length -
                                        1
                                    }
                                    onClick={() =>
                                      moveUpstreamHeaderRule(ruleIndex, 1)
                                    }
                                  >
                                    <ArrowDown data-icon="inline-start" />
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="icon"
                                    className="text-muted-foreground"
                                    aria-label={titleForLocale(
                                      locale,
                                      "删除规则",
                                      "Remove rule",
                                    )}
                                    onClick={() =>
                                      removeUpstreamHeaderRule(ruleIndex)
                                    }
                                  >
                                    <Trash2 data-icon="inline-start" />
                                  </Button>
                                </div>
                              </div>
                              {rule.matchType === "exact" ? (
                                <Field>
                                  <FieldLabel>
                                    {titleForLocale(
                                      locale,
                                      "模型名称",
                                      "Models",
                                    )}
                                  </FieldLabel>
                                  <Textarea
                                    className="min-h-[84px]"
                                    value={rule.models}
                                    onChange={(event) =>
                                      updateUpstreamHeaderRule(ruleIndex, {
                                        models: event.target.value,
                                      })
                                    }
                                    placeholder={"gpt-5.5\ngpt-5.4-mini"}
                                  />
                                </Field>
                              ) : (
                                <Field>
                                  <FieldLabel>
                                    {titleForLocale(
                                      locale,
                                      "模型正则",
                                      "Model regex",
                                    )}
                                  </FieldLabel>
                                  <Input
                                    value={rule.pattern}
                                    onChange={(event) =>
                                      updateUpstreamHeaderRule(ruleIndex, {
                                        pattern: event.target.value,
                                      })
                                    }
                                    placeholder="^claude-"
                                  />
                                </Field>
                              )}
                              <HeaderRows
                                title={titleForLocale(
                                  locale,
                                  "规则请求头",
                                  "Rule headers",
                                )}
                                headers={rule.headers}
                                locale={locale}
                                onAdd={() =>
                                  updateUpstreamHeaderRule(ruleIndex, {
                                    headers: [
                                      ...rule.headers,
                                      { key: "", value: "" },
                                    ],
                                  })
                                }
                                onUpdate={(headerIndex, patch) =>
                                  updateRuleHeader(
                                    ruleIndex,
                                    headerIndex,
                                    patch,
                                  )
                                }
                                onRemove={(headerIndex) =>
                                  removeRuleHeader(ruleIndex, headerIndex)
                                }
                              />
                            </div>
                          ),
                        )}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">
                        {titleForLocale(locale, "暂无规则", "No rules")}
                      </div>
                    )}
                  </div>
                </FieldGroup>
              </SettingCard>
            </TabsContent>

            <TabsContent value="model-test" className="mt-0">
              <SettingCard
                title={titleForLocale(locale, "模型测试", "Model test")}
                description={settingsTabs[4].description}
              >
                <FieldGroup>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "预设问题", "Preset prompts")}
                    </FieldLabel>
                    <Textarea
                      className="min-h-[132px]"
                      value={draft.modelTestPrompts}
                      onChange={(event) =>
                        setDraftValue("modelTestPrompts", event.target.value)
                      }
                      placeholder={DEFAULT_MODEL_TEST_PROMPTS.join("\n")}
                    />
                  </Field>
                </FieldGroup>
              </SettingCard>
            </TabsContent>

            <TabsContent value="circuit-breaker" className="mt-0">
              <SettingCard
                title={titleForLocale(locale, "熔断器", "Circuit breaker")}
                description={settingsTabs[5].description}
              >
                <FieldGroup>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "失败阈值", "Failure threshold")}
                    </FieldLabel>
                    <Input
                      type="number"
                      min="0"
                      value={draft.circuitBreakerThreshold}
                      onChange={(event) =>
                        setDraftValue(
                          "circuitBreakerThreshold",
                          event.target.value,
                        )
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(
                        locale,
                        "基础冷却秒数",
                        "Cooldown seconds",
                      )}
                    </FieldLabel>
                    <Input
                      type="number"
                      min="0"
                      value={draft.circuitBreakerCooldown}
                      onChange={(event) =>
                        setDraftValue(
                          "circuitBreakerCooldown",
                          event.target.value,
                        )
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(
                        locale,
                        "最大冷却秒数",
                        "Max cooldown seconds",
                      )}
                    </FieldLabel>
                    <Input
                      type="number"
                      min="0"
                      value={draft.circuitBreakerMaxCooldown}
                      onChange={(event) =>
                        setDraftValue(
                          "circuitBreakerMaxCooldown",
                          event.target.value,
                        )
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(
                        locale,
                        "健康窗口秒数",
                        "Health window seconds",
                      )}
                    </FieldLabel>
                    <Input
                      type="number"
                      min="1"
                      value={draft.healthWindowSeconds}
                      onChange={(event) =>
                        setDraftValue("healthWindowSeconds", event.target.value)
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(
                        locale,
                        "健康惩罚权重",
                        "Health penalty weight",
                      )}
                    </FieldLabel>
                    <Input
                      type="number"
                      min="0"
                      step="0.1"
                      value={draft.healthPenaltyWeight}
                      onChange={(event) =>
                        setDraftValue("healthPenaltyWeight", event.target.value)
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(
                        locale,
                        "健康最小样本数",
                        "Health min samples",
                      )}
                    </FieldLabel>
                    <Input
                      type="number"
                      min="1"
                      value={draft.healthMinSamples}
                      onChange={(event) =>
                        setDraftValue("healthMinSamples", event.target.value)
                      }
                    />
                  </Field>
                </FieldGroup>
              </SettingCard>
            </TabsContent>
          </div>
        </Tabs>
      </section>
    </>
  );
}
