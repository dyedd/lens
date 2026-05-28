"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ChevronDown,
  Ellipsis,
  Filter,
  Globe2,
  KeyRound,
  Plus,
  RefreshCcw,
  Server,
  Trash2,
  Waypoints,
  X,
} from "lucide-react";
import { toast } from "sonner";
import {
  ApiError,
  ProtocolKind,
  RouteSnapshot,
  Site,
  SiteBaseUrlInput,
  SiteCredentialInput,
  SiteModelFetchItem,
  SiteModelFetchPayload,
  SiteModelTestPayload,
  SiteModelTestResult,
  SitePayload,
  SiteModelInput,
  SiteRuntimeSummary,
  SettingItem,
  apiRequest,
} from "@/lib/api";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import { useI18n } from "@/lib/i18n";
import {
  MODEL_TEST_PROMPTS_SETTING_KEY,
  parseModelTestPrompts,
} from "@/lib/model-test-prompts";
import { cn } from "@/lib/utils";
import { useAppTimeZone } from "@/hooks/use-app-time-zone";
import { Badge } from "@/components/ui/badge";
import { Dialog, AppDialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemFooter,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ToolbarSearchInput } from "@/components/ui/toolbar-search-input";

const protocolOptions: Array<{ value: ProtocolKind; label: string }> = [
  { value: "openai_chat", label: "OpenAI Chat" },
  { value: "openai_responses", label: "OpenAI Responses" },
  { value: "openai_embedding", label: "OpenAI Embedding" },
  { value: "rerank", label: "Rerank" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Gemini" },
];

type HeaderItem = { key: string; value: string };
type FormCredential = Omit<SiteCredentialInput, "id"> & { id: string };
type FormBaseUrl = Omit<SiteBaseUrlInput, "id"> & {
  id: string;
  compatible_protocols: ProtocolKind[];
};
type ChannelHealthRow = RouteSnapshot["health"][number];
type ChannelRuntimeSummary = SiteRuntimeSummary["channel_summaries"][number];
type ChannelHealthBucket = ChannelRuntimeSummary["health_buckets"][number];
type CoolingBadgeSpec = {
  label: string;
  title: string;
  className: string;
};
type Locale = "zh-CN" | "en-US";
const CHANNEL_HEALTH_BUCKET_COUNT = 12;

function createLocalId(prefix: string) {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

type FormCombo = {
  id?: string | null;
  name: string;
  enabled: boolean;
  headers: HeaderItem[];
  channel_proxy: string;
  param_override: string;
  match_regex: string;
  manual_model_name: string;
  base_url_id: string;
  credential_id: string;
  models: SiteModelInput[];
  expanded: boolean;
};

type FormState = {
  name: string;
  base_urls: FormBaseUrl[];
  credentials: FormCredential[];
  combos: FormCombo[];
};

type PickerModelItem = {
  protocol: ProtocolKind;
  credential_id: string;
  model_name: string;
};

type PickerModelGroup = {
  credential_id: string;
  model_name: string;
  protocols: ProtocolKind[];
};

function genericModelKey(
  model: Pick<PickerModelItem, "credential_id" | "model_name">,
) {
  return `${model.credential_id}:${model.model_name}`;
}

function pickerModelKey(
  model: Pick<PickerModelItem, "credential_id" | "model_name">,
) {
  return genericModelKey(model);
}

function groupPickerModels(models: PickerModelItem[]) {
  const groups = new Map<string, PickerModelGroup>();
  for (const model of models) {
    const key = genericModelKey(model);
    const group = groups.get(key);
    if (group) {
      if (!group.protocols.includes(model.protocol)) {
        group.protocols.push(model.protocol);
      }
      continue;
    }
    groups.set(key, {
      credential_id: model.credential_id,
      model_name: model.model_name,
      protocols: [model.protocol],
    });
  }
  return Array.from(groups.values());
}

function pickerModelKeys(models: PickerModelItem[]) {
  return Array.from(new Set(models.map((item) => pickerModelKey(item))));
}

function mergedModelProtocol(
  currentProtocol: ProtocolKind | null | undefined,
  incomingProtocols: ProtocolKind[],
) {
  if (
    currentProtocol &&
    incomingProtocols.length === 1 &&
    incomingProtocols[0] === currentProtocol
  ) {
    return currentProtocol;
  }
  return undefined;
}

type ModelTestTarget = {
  protocolIndex: number;
  modelIndex: number;
};

type SiteRow = Site & {
  subtitle: string;
  protocol_count: number;
  credential_count: number;
  model_count: number;
  endpoint_summary: string;
};

type ChannelStatusFilter = "all" | "enabled" | "disabled";
type ChannelSort =
  | "requests-desc"
  | "name-asc"
  | "name-desc"
  | "models-desc"
  | "protocols-desc";

const emptyCombo = (baseUrlId = "", name = ""): FormCombo => ({
  id: null,
  name,
  enabled: true,
  headers: [{ key: "", value: "" }],
  channel_proxy: "",
  param_override: "",
  match_regex: "",
  manual_model_name: "",
  base_url_id: baseUrlId,
  credential_id: "",
  models: [],
  expanded: true,
});

const emptyForm = (locale: Locale = "zh-CN"): FormState => {
  const baseUrlId = createLocalId("baseurl");
  return {
    name: "",
    base_urls: [{ id: baseUrlId, url: "", name: "", enabled: true, compatible_protocols: [] }],
    credentials: [
      { id: createLocalId("credential"), name: "", api_key: "", enabled: true },
    ],
    combos: [emptyCombo(baseUrlId, defaultComboName(0, locale))],
  };
};

function protocolLabel(protocol: ProtocolKind) {
  return (
    protocolOptions.find((item) => item.value === protocol)?.label ?? protocol
  );
}

function compactProtocolLabel(protocol: ProtocolKind) {
  switch (protocol) {
    case "openai_chat":
      return "chat";
    case "openai_responses":
      return "responses";
    case "openai_embedding":
      return "embeddings";
    case "rerank":
      return "rerank";
    case "anthropic":
      return "anthropic";
    case "gemini":
      return "gemini";
    default:
      return protocol;
  }
}

function isGeneratedCredentialName(value: string) {
  const normalized = value.trim().toLowerCase();
  return (
    normalized === "默认密钥" ||
    /^key\s*\d+$/.test(normalized) ||
    /^密钥\s*\d+$/.test(value.trim())
  );
}

function fallbackCredentialName(index: number) {
  return `Key ${index + 1}`;
}

function credentialIndexLabel(index: number, locale: string) {
  return locale === "zh-CN" ? `密钥 ${index + 1}` : `Key ${index + 1}`;
}

function credentialLabel(
  item: { name: string },
  index: number,
  locale: string,
) {
  const name = item.name.trim();
  if (name) return name;
  return credentialIndexLabel(index, locale);
}

function baseUrlIndexLabel(index: number, locale: string) {
  return locale === "zh-CN" ? `地址 ${index + 1}` : `URL ${index + 1}`;
}

function baseUrlLabel(item: { name: string }, index: number, locale: string) {
  const name = item.name.trim();
  if (name) return name;
  return baseUrlIndexLabel(index, locale);
}

function defaultComboName(index: number, locale: string) {
  return locale === "zh-CN" ? `组合 ${index + 1}` : `Combo ${index + 1}`;
}

function comboDisplayName(
  item: { name?: string | null },
  index: number,
  locale: string,
) {
  const name = safeText(item.name).trim();
  return name || defaultComboName(index, locale);
}

function nextComboName(
  combos: Array<{ name?: string | null }>,
  locale: string,
) {
  const usedNames = new Set(
    combos
      .map((item, index) => comboDisplayName(item, index, locale).toLowerCase())
      .filter(Boolean),
  );
  for (let index = combos.length; index < combos.length + 1000; index += 1) {
    const candidate = defaultComboName(index, locale);
    if (!usedNames.has(candidate.toLowerCase())) {
      return candidate;
    }
  }
  return defaultComboName(combos.length, locale);
}

function defaultBaseUrlId(items: Array<{ id: string; enabled: boolean }>) {
  return items.find((item) => item.enabled)?.id ?? items[0]?.id ?? "";
}

function resolveBaseUrlId(
  items: Array<{ id: string; enabled: boolean }>,
  baseUrlId: string,
) {
  return items.some((item) => item.id === baseUrlId)
    ? baseUrlId
    : defaultBaseUrlId(items);
}

function activeBaseUrlValue(
  form: FormState,
  protocol: Pick<FormCombo, "base_url_id">,
) {
  const boundBaseUrl = protocol.base_url_id
    ? form.base_urls.find((item) => item.id === protocol.base_url_id)
    : undefined;
  if (boundBaseUrl?.url) return boundBaseUrl.url;
  const enabledUrl = form.base_urls.find(
    (item) => item.enabled && item.url.trim(),
  )?.url;
  if (enabledUrl) return enabledUrl;
  return form.base_urls[0]?.url || "";
}

function formHeaders(protocol: Pick<FormCombo, "headers">) {
  return Object.fromEntries(
    protocol.headers
      .map((entry) => [entry.key.trim(), entry.value] as const)
      .filter(([key]) => key),
  );
}

function credentialDisplayName(
  credential: Site["credentials"][number] | undefined,
  index: number,
  locale: Locale,
) {
  if (!credential) {
    return locale === "zh-CN" ? `密钥 ${index + 1}` : `Key ${index + 1}`;
  }
  if (!credential.name.trim() || isGeneratedCredentialName(credential.name)) {
    return locale === "zh-CN" ? `密钥 ${index + 1}` : `Key ${index + 1}`;
  }
  return credential.name.trim();
}

function safeText(value: string | null | undefined) {
  return typeof value === "string" ? value : "";
}

function formatCooldownDuration(seconds: number) {
  const value = Math.max(Math.floor(seconds), 0);
  if (value < 60) return `${value}s`;

  const minutes = Math.floor(value / 60);
  const remainingSeconds = value % 60;
  if (minutes < 60) {
    return remainingSeconds
      ? `${minutes}m ${remainingSeconds}s`
      : `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

function modelBadgeClassName(enabled: boolean) {
  return enabled
    ? "inline-flex h-8 items-center gap-2 rounded-full border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-muted"
    : "inline-flex h-8 items-center gap-2 rounded-full border bg-muted/40 px-3 text-sm font-medium text-muted-foreground";
}

function selectClassName() {
  return "w-full [&_select]:border-border [&_select]:bg-background [&_select]:text-sm [&_select]:text-foreground";
}

function siteSubtitle(site: Site) {
  const protocols = Array.from(
    new Set(site.base_urls.flatMap((b) => b.compatible_protocols)),
  );
  return protocols.map(protocolLabel).join(" / ");
}

function siteEndpointSummary(site: Site, locale: string = "zh-CN") {
  const enabled = site.base_urls.filter((item) => item.enabled);
  const firstUrl = enabled[0]?.url || site.base_urls[0]?.url || "";
  const extraCount =
    enabled.length > 1
      ? enabled.length - 1
      : site.base_urls.length > 1
        ? site.base_urls.length - 1
        : 0;
  if (extraCount > 0) {
    const suffix =
      locale === "zh-CN" ? ` + ${extraCount}个地址` : ` + ${extraCount} more`;
    return firstUrl + suffix;
  }
  return firstUrl;
}

function siteModelCount(site: Site) {
  return site.protocols.reduce(
    (total, protocol) =>
      total + protocol.models.filter((item) => item.enabled).length,
    0,
  );
}

function isSiteEnabled(site: Site) {
  return site.protocols.some((item) => item.enabled);
}

function protocolBadgeClassName(protocol: ProtocolKind) {
  switch (protocol) {
    case "openai_chat":
      return "border-transparent bg-sky-500/10 text-sky-700";
    case "openai_responses":
      return "border-transparent bg-indigo-500/10 text-indigo-700";
    case "openai_embedding":
      return "border-transparent bg-cyan-500/10 text-cyan-700";
    case "rerank":
      return "border-transparent bg-violet-500/10 text-violet-700";
    case "anthropic":
      return "border-transparent bg-amber-500/10 text-amber-700";
    case "gemini":
      return "border-transparent bg-emerald-500/10 text-emerald-700";
    default:
      return "border-transparent bg-secondary text-secondary-foreground";
  }
}

function ChannelMetric({
  icon,
  label,
  value,
  tone = "default",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: "default" | "accent";
}) {
  return (
    <div
      className={cn(
        "inline-flex min-h-8 min-w-0 max-w-full items-center gap-2 rounded-full border px-3 text-xs",
        tone === "accent"
          ? "border-primary/20 bg-primary/[0.07] text-primary"
          : "border-border/70 bg-muted/25 text-muted-foreground",
      )}
    >
      <span className="inline-flex size-4.5 shrink-0 items-center justify-center">
        {icon}
      </span>
      <span className="min-w-0 truncate font-medium">
        {label} {value}
      </span>
    </div>
  );
}

function getSiteFaviconCandidates(url: string) {
  try {
    const parsed = new URL(url);
    return [
      `${parsed.origin}/favicon.ico`,
      `https://www.google.com/s2/favicons?domain=${parsed.hostname}&sz=64`,
    ];
  } catch {
    return [];
  }
}

function SiteFavicon({ url, name }: { url: string; name: string }) {
  const [candidateIndex, setCandidateIndex] = useState(0);
  const candidates = getSiteFaviconCandidates(url);
  const currentSrc = candidates[candidateIndex];

  return (
    <span className="flex size-11 items-center justify-center rounded-xl border bg-background/80">
      {currentSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={currentSrc}
          alt=""
          className="size-5 rounded-sm object-contain"
          loading="lazy"
          onError={() => {
            setCandidateIndex((current) =>
              current < candidates.length - 1 ? current + 1 : current,
            );
          }}
        />
      ) : (
        <Globe2 aria-hidden="true" className="text-muted-foreground" />
      )}
      <span className="sr-only">{name}</span>
    </span>
  );
}

function maxKeyCooldownSeconds(health: ChannelHealthRow | undefined) {
  if (!health?.key_health?.length) {
    return 0;
  }
  return Math.max(
    0,
    ...health.key_health.map((item) => item.cooldown_remaining_seconds),
  );
}

function keyCooldownDetails(
  site: SiteRow,
  health: ChannelHealthRow,
  locale: Locale,
) {
  const credentialById = new Map(
    site.credentials.map((item) => [item.id, item] as const),
  );
  const credentialIndexById = new Map(
    site.credentials.map((item, index) => [item.id, index] as const),
  );

  return health.key_health
    .filter((item) => !item.available && item.cooldown_remaining_seconds > 0)
    .sort(
      (left, right) =>
        right.cooldown_remaining_seconds - left.cooldown_remaining_seconds,
    )
    .map((item) => {
      const credentialIndex = credentialIndexById.get(item.credential_id) ?? 0;
      const credentialName = credentialDisplayName(
        credentialById.get(item.credential_id),
        credentialIndex,
        locale,
      );
      const duration = formatCooldownDuration(item.cooldown_remaining_seconds);
      return `${credentialName} ${locale === "zh-CN" ? "冷却剩余" : "cooldown remaining"} ${duration}`;
    });
}

function resolveCoolingBadge(
  site: SiteRow,
  health: ChannelHealthRow | undefined,
  locale: Locale,
): CoolingBadgeSpec | null {
  if (!health) {
    return null;
  }
  if (health.cooldown_remaining_seconds > 0) {
    const duration = formatCooldownDuration(health.cooldown_remaining_seconds);
    return locale === "zh-CN"
      ? {
          label: `冷却 ${duration}`,
          title: `渠道冷却剩余 ${duration}`,
          className: "border-transparent bg-destructive/12 text-destructive",
        }
      : {
          label: `Cooling ${duration}`,
          title: `Channel cooldown remaining ${duration}`,
          className: "border-transparent bg-destructive/12 text-destructive",
        };
  }
  const keyCooldownSeconds = maxKeyCooldownSeconds(health);
  if (keyCooldownSeconds > 0) {
    const duration = formatCooldownDuration(keyCooldownSeconds);
    const details = keyCooldownDetails(site, health, locale).join("\n");
    return locale === "zh-CN"
      ? {
          label: `Key 冷却 ${duration}`,
          title: details || `Key 冷却剩余 ${duration}`,
          className: "border-transparent bg-amber-500/12 text-amber-700",
        }
      : {
          label: `Key cooling ${duration}`,
          title: details || `Key cooldown remaining ${duration}`,
          className: "border-transparent bg-amber-500/12 text-amber-700",
        };
  }
  return null;
}

function normalizedBucketCounts(bucket: ChannelHealthBucket) {
  const total = Math.max(0, bucket.total_count);
  return {
    total,
    success: Math.min(Math.max(0, bucket.success_count), total),
  };
}

function healthBucketTone(bucket: ChannelHealthBucket) {
  const { success, total } = normalizedBucketCounts(bucket);
  if (total <= 0) {
    return "bg-muted/70";
  }
  if (success >= total) {
    return "bg-emerald-500";
  }
  if (success > 0) {
    return "bg-amber-500";
  }
  return "bg-destructive";
}

function createHealthBucketTimeFormatter(locale: Locale, timeZone?: string) {
  return new Intl.DateTimeFormat(locale === "zh-CN" ? "zh-CN" : "en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...(timeZone ? { timeZone } : {}),
  });
}

function formatHealthBucketRange(
  bucket: ChannelHealthBucket,
  formatDateTime: Intl.DateTimeFormat,
) {
  return `${formatDateTime.format(new Date(bucket.started_at))} - ${formatDateTime.format(new Date(bucket.ended_at))}`;
}

function SiteHealthPreview({
  site,
  summary,
  healthByChannelId,
  locale,
  timeZone,
}: {
  site: SiteRow;
  summary?: SiteRuntimeSummary;
  healthByChannelId: Map<string, ChannelHealthRow>;
  locale: Locale;
  timeZone?: string;
}) {
  const enabledProtocols = site.protocols.filter((item) => item.enabled);
  const summaryByChannelId = new Map(
    (summary?.channel_summaries ?? []).map(
      (item) => [item.channel_id, item] as const,
    ),
  );
  const multiProtocol = enabledProtocols.length > 1;
  const bucketTimeFormatter = createHealthBucketTimeFormatter(locale, timeZone);

  if (!enabledProtocols.length) {
    return (
      <div className="mt-3 text-xs text-muted-foreground">
        {locale === "zh-CN" ? "暂无健康数据" : "No health data"}
      </div>
    );
  }

  return (
    <div className="mt-3 flex flex-col gap-2.5">
      <div className="text-xs font-medium text-muted-foreground">
        {locale === "zh-CN" ? "健康状态" : "Health"}
      </div>
      {enabledProtocols.map((protocol) => {
        const protocolIndex = Math.max(
          site.protocols.findIndex((item) => item.id === protocol.id),
          0,
        );
        const health = healthByChannelId.get(protocol.id);
        const channelSummary = summaryByChannelId.get(protocol.id);
        const buckets = (channelSummary?.health_buckets ?? []).slice(
          -CHANNEL_HEALTH_BUCKET_COUNT,
        );
        const coolingBadge = resolveCoolingBadge(site, health, locale);
        const segments = [
          ...Array.from(
            {
              length: Math.max(CHANNEL_HEALTH_BUCKET_COUNT - buckets.length, 0),
            },
            (_, index) => ({
              key: `${protocol.id}-placeholder-${index}`,
              bucket: null,
            }),
          ),
          ...buckets.map((bucket, index) => ({
            key: `${protocol.id}-bucket-${bucket.started_at}-${index}`,
            bucket,
          })),
        ];

        return (
          <div
            key={protocol.id}
            className="flex min-w-0 flex-wrap items-center gap-3 py-0.5"
          >
            {multiProtocol ? (
              <span className="w-28 min-w-0 shrink-0 truncate text-[11px] font-medium text-muted-foreground">
                {comboDisplayName(protocol, protocolIndex, locale)}
              </span>
            ) : null}

            <div
              className="flex min-w-0 flex-1 items-end gap-1"
              aria-label={locale === "zh-CN" ? "健康状态" : "health history"}
            >
              {segments.map((segment) => {
                if (!segment.bucket) {
                  return (
                    <span
                      key={segment.key}
                      className="block h-6 w-1.5 rounded-[3px] bg-muted/70"
                      aria-hidden
                    />
                  );
                }

                const { success, total } = normalizedBucketCounts(
                  segment.bucket,
                );
                const bucketRange = formatHealthBucketRange(
                  segment.bucket,
                  bucketTimeFormatter,
                );

                const tooltipContent = (
                  <TooltipContent
                    side="bottom"
                    sideOffset={8}
                    collisionPadding={12}
                    className="flex flex-col items-start gap-1 px-3 py-2 text-left text-xs"
                  >
                    <div className="font-medium">{bucketRange}</div>
                    <div className="text-muted-foreground">
                      {locale === "zh-CN" ? "成功" : "Success"}: {success}/
                      {total}
                    </div>
                  </TooltipContent>
                );

                const segmentClassName = cn(
                  "block h-6 w-1.5 appearance-none rounded-[3px] border-0 p-0",
                  healthBucketTone(segment.bucket),
                );

                return (
                  <Tooltip key={segment.key}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          segmentClassName,
                          "outline-none transition-transform hover:scale-y-110 focus-visible:ring-2 focus-visible:ring-ring/70 focus-visible:ring-offset-1",
                        )}
                        onClick={(event) => event.stopPropagation()}
                        onKeyDown={(event) => event.stopPropagation()}
                        aria-label={`${bucketRange} ${success}/${total}`}
                      />
                    </TooltipTrigger>
                    {tooltipContent}
                  </Tooltip>
                );
              })}
            </div>

            <div className="flex w-full min-w-0 flex-wrap items-center gap-2 sm:ml-auto sm:w-auto sm:shrink-0">
              {coolingBadge ? (
                <Badge
                  variant="outline"
                  title={coolingBadge.title}
                  className={cn(
                    "max-w-full truncate px-2.5 py-1 text-xs",
                    coolingBadge.className,
                  )}
                >
                  {coolingBadge.label}
                </Badge>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function toForm(site: Site, locale: Locale = "zh-CN"): FormState {
  const baseUrls = site.base_urls.length
    ? site.base_urls.map((item) => ({
        id: item.id,
        url: item.url,
        name: item.name,
        enabled: item.enabled,
        compatible_protocols: item.compatible_protocols ?? [],
      }))
    : [{ id: createLocalId("baseurl"), url: "", name: "", enabled: true, compatible_protocols: [] as ProtocolKind[] }];
  return {
    name: site.name,
    base_urls: baseUrls,
    credentials: site.credentials.map((item) => ({
      id: item.id,
      name: isGeneratedCredentialName(item.name) ? "" : item.name,
      api_key: item.api_key,
      enabled: item.enabled,
    })),
    combos: site.protocols.map((item, itemIndex) => ({
      id: item.id,
      name: comboDisplayName(item, itemIndex, locale),
      enabled: item.enabled,
      headers: Object.entries(item.headers).length
        ? Object.entries(item.headers).map(([key, value]) => ({ key, value }))
        : [{ key: "", value: "" }],
      channel_proxy: item.channel_proxy,
      param_override: item.param_override,
      match_regex: safeText(item.match_regex),
      manual_model_name: "",
      base_url_id: resolveBaseUrlId(baseUrls, item.base_url_id),
      credential_id: item.credential_id,
      models: item.models.map((model) => ({
        id: model.id,
        protocol: model.protocol,
        credential_id: model.credential_id,
        model_name: model.model_name,
        enabled: model.enabled,
      })),
      expanded: true,
    })),
  };
}

function formBaseUrlsForPayload(form: FormState) {
  return form.base_urls
    .map((item) => ({
      id: item.id,
      url: item.url.trim(),
      name: item.name.trim(),
      enabled: item.enabled,
      compatible_protocols: item.compatible_protocols,
    }))
    .filter((item) => item.url);
}

function toPayload(form: FormState): SitePayload {
  const baseUrls = formBaseUrlsForPayload(form);
  return {
    name: form.name.trim(),
    base_urls: baseUrls,
    credentials: form.credentials
      .map((item, index) => ({
        id: item.id,
        name: item.name.trim() || fallbackCredentialName(index),
        api_key: item.api_key.trim(),
        enabled: item.enabled,
      }))
      .filter((item) => item.api_key),
    protocols: form.combos.map((item) => {
      const credentialId = effectiveProtocolCredentialId(
        item,
        form.credentials,
      );
      return {
        id: item.id,
        name: item.name.trim(),
        enabled: item.enabled,
        headers: Object.fromEntries(
          item.headers
            .map((entry) => [entry.key.trim(), entry.value] as const)
            .filter(([key]) => key),
        ),
        channel_proxy: item.channel_proxy.trim(),
        param_override: item.param_override.trim(),
        match_regex: safeText(item.match_regex).trim(),
        base_url_id: item.base_url_id,
        credential_id: credentialId,
        models: item.models
          .map((model) => ({
            id: model.id,
            protocol: model.protocol,
            credential_id: model.credential_id,
            model_name: model.model_name.trim(),
            enabled: model.enabled,
          }))
          .filter(
            (model) =>
              model.credential_id === credentialId && model.model_name,
          ),
      };
    }),
  };
}

function effectiveProtocolCredentialId(
  protocol: Pick<FormCombo, "credential_id">,
  credentials: Array<Pick<FormCredential, "id" | "api_key">>,
) {
  const credentialIds = credentials
    .filter((item) => item.api_key.trim())
    .map((item) => item.id);
  return credentialIds.includes(protocol.credential_id)
    ? protocol.credential_id
    : "";
}

function comboCredentialKeys(
  combo: FormCombo,
  baseUrlIds: Set<string>,
) {
  if (!baseUrlIds.has(combo.base_url_id)) return [];
  return [[combo.base_url_id, combo.credential_id].join(":")];
}

function duplicateComboKeys(
  combos: FormCombo[],
  baseUrls: Array<{ id: string }>,
) {
  const baseUrlIds = new Set(baseUrls.map((item) => item.id));
  const counts = new Map<string, number>();
  for (const item of combos) {
    for (const key of comboCredentialKeys(item, baseUrlIds)) {
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return new Set(
    [...counts.entries()].filter(([, count]) => count > 1).map(([key]) => key),
  );
}

function invalidProtocolBaseUrlCount(form: FormState) {
  const baseUrlIds = new Set(formBaseUrlsForPayload(form).map((item) => item.id));
  return form.combos.filter((item) => !baseUrlIds.has(item.base_url_id)).length;
}

function SwitchButton({
  checked,
  onChange,
  disabled = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <Switch checked={checked} disabled={disabled} onCheckedChange={onChange} />
  );
}

function ChannelFiltersPanel({
  locale,
  search,
  statusFilter,
  protocolFilter,
  sortBy,
  activeFilterCount,
  onSearchChange,
  onStatusChange,
  onProtocolChange,
  onSortChange,
  onReset,
}: {
  locale: Locale;
  search: string;
  statusFilter: ChannelStatusFilter;
  protocolFilter: "all" | ProtocolKind;
  sortBy: ChannelSort;
  activeFilterCount: number;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: ChannelStatusFilter) => void;
  onProtocolChange: (value: "all" | ProtocolKind) => void;
  onSortChange: (value: ChannelSort) => void;
  onReset: () => void;
}) {
  return (
    <div className="rounded-2xl border bg-card p-4 xl:sticky xl:top-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex size-9 items-center justify-center rounded-xl bg-primary/[0.08] text-primary">
            <Filter size={16} />
          </span>
          <div>
            <div className="text-sm font-semibold text-foreground">
              {locale === "zh-CN" ? "筛选" : "Filters"}
            </div>
            <div className="text-xs text-muted-foreground">
              {locale === "zh-CN"
                ? `已启用 ${activeFilterCount} 项`
                : `${activeFilterCount} active`}
            </div>
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onReset}
          disabled={!activeFilterCount && sortBy === "requests-desc"}
        >
          {locale === "zh-CN" ? "清空" : "Clear"}
        </Button>
      </div>

      <FieldSet className="gap-4">
        <FieldLegend>
          {locale === "zh-CN" ? "筛选条件" : "Refine results"}
        </FieldLegend>
        <FieldGroup className="gap-4">
          <Field>
            <FieldLabel>{locale === "zh-CN" ? "关键词" : "Keyword"}</FieldLabel>
            <ToolbarSearchInput
              value={search}
              onChange={onSearchChange}
              onClear={() => onSearchChange("")}
              placeholder={
                locale === "zh-CN"
                  ? "渠道 / 协议 / 模型"
                  : "Channel / protocol / model"
              }
              className="max-w-none"
            />
          </Field>

          <Field>
            <FieldLabel>{locale === "zh-CN" ? "状态" : "Status"}</FieldLabel>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {[
                {
                  key: "all" as const,
                  label: locale === "zh-CN" ? "全部" : "All",
                },
                {
                  key: "enabled" as const,
                  label: locale === "zh-CN" ? "启用" : "Enabled",
                },
                {
                  key: "disabled" as const,
                  label: locale === "zh-CN" ? "停用" : "Disabled",
                },
              ].map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  variant={statusFilter === option.key ? "default" : "outline"}
                  size="sm"
                  onClick={() => onStatusChange(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </Field>

          <Field>
            <FieldLabel htmlFor="channels-protocol-filter">
              {locale === "zh-CN" ? "协议" : "Protocol"}
            </FieldLabel>
            <NativeSelect
              id="channels-protocol-filter"
              className="w-full"
              value={protocolFilter}
              onChange={(event) =>
                onProtocolChange(event.target.value as "all" | ProtocolKind)
              }
            >
              <NativeSelectOption value="all">
                {locale === "zh-CN" ? "全部协议" : "All protocols"}
              </NativeSelectOption>
              {protocolOptions.map((option) => (
                <NativeSelectOption key={option.value} value={option.value}>
                  {option.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </Field>

          <Field>
            <FieldLabel htmlFor="channels-sort">
              {locale === "zh-CN" ? "排序" : "Sort by"}
            </FieldLabel>
            <NativeSelect
              id="channels-sort"
              className="w-full"
              value={sortBy}
              onChange={(event) =>
                onSortChange(event.target.value as ChannelSort)
              }
            >
              <NativeSelectOption value="requests-desc">
                {locale === "zh-CN" ? "请求优先" : "Requests first"}
              </NativeSelectOption>
              <NativeSelectOption value="models-desc">
                {locale === "zh-CN" ? "模型优先" : "Models first"}
              </NativeSelectOption>
              <NativeSelectOption value="protocols-desc">
                {locale === "zh-CN" ? "协议优先" : "Protocols first"}
              </NativeSelectOption>
              <NativeSelectOption value="name-asc">
                {locale === "zh-CN" ? "名称升序" : "Name asc"}
              </NativeSelectOption>
              <NativeSelectOption value="name-desc">
                {locale === "zh-CN" ? "名称降序" : "Name desc"}
              </NativeSelectOption>
            </NativeSelect>
          </Field>
        </FieldGroup>
      </FieldSet>
    </div>
  );
}

function ComboConfigItem({
  form,
  combo,
  comboIndex,
  locale,
  fetchingProtocolIndex,
  duplicatedComboKeys,
  onUpdateCombo,
  onRemoveCombo,
  onAddManualModel,
  onFetchModels,
  onOpenAdvanced,
  onOpenModelTest,
}: {
  form: FormState;
  combo: FormCombo;
  comboIndex: number;
  locale: Locale;
  fetchingProtocolIndex: number | null;
  duplicatedComboKeys: Set<string>;
  onUpdateCombo: (index: number, patch: Partial<FormCombo>) => void;
  onRemoveCombo: (index: number) => void;
  onAddManualModel: (index: number, credentialId: string) => void;
  onFetchModels: (index: number) => void;
  onOpenAdvanced: (index: number) => void;
  onOpenModelTest: (comboIndex: number, modelIndex: number) => void;
}) {
  const submittedBaseUrls = formBaseUrlsForPayload(form);
  const submittedBaseUrlIds = new Set(submittedBaseUrls.map((item) => item.id));
  const comboDuplicated = comboCredentialKeys(
    combo,
    submittedBaseUrlIds,
  ).some((key) => duplicatedComboKeys.has(key));
  const activeCredentialIds = new Set(
    form.credentials
      .filter((item) => item.enabled && item.api_key.trim())
      .map((item) => item.id),
  );
  const credentialOptions = form.credentials
    .map((item, index) => ({
      ...item,
      display_name: credentialLabel(item, index, locale),
    }))
    .filter((item) => item.api_key.trim());
  const selectedCredentialId = combo.credential_id;
  const selectedCredentialActive = activeCredentialIds.has(selectedCredentialId);
  const selectedCredentialKnown = credentialOptions.some(
    (item) => item.id === selectedCredentialId,
  );
  const credentialLabelsById = new Map(
    credentialOptions.map((item) => [item.id, item.display_name] as const),
  );
  const visibleModels = combo.models
    .map((model, modelIndex) => ({ model, modelIndex }))
    .filter(
      ({ model }) =>
        selectedCredentialId && model.credential_id === selectedCredentialId,
    );

  return (
    <div className="grid gap-3 border-b pb-4 last:border-b-0 last:pb-0">
      <div className="flex flex-col gap-3">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,1fr)_32px_auto] xl:items-end">
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "组合名称" : "Combo name"}
            </FieldLabel>
            <Input
              className="w-full min-w-0"
              value={combo.name}
              onChange={(event) =>
                onUpdateCombo(comboIndex, {
                  name: event.target.value,
                })
              }
              placeholder={defaultComboName(comboIndex, locale)}
            />
          </Field>
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "地址来源" : "Base URL"}
            </FieldLabel>
            <NativeSelect
              className={selectClassName()}
              value={resolveBaseUrlId(form.base_urls, combo.base_url_id)}
              onChange={(event) =>
                onUpdateCombo(comboIndex, {
                  base_url_id: event.target.value,
                })
              }
            >
              {form.base_urls.map((item, baseUrlIndex) => (
                <NativeSelectOption key={item.id} value={item.id}>
                  {baseUrlLabel(item, baseUrlIndex, locale)}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </Field>
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "密钥" : "Key"}
            </FieldLabel>
            <NativeSelect
              className={selectClassName()}
              value={selectedCredentialId}
              onChange={(event) => {
                const credentialId = event.target.value;
                onUpdateCombo(comboIndex, {
                  credential_id: credentialId,
                  models: combo.models.filter(
                    (model) => model.credential_id === credentialId,
                  ),
                });
              }}
            >
              <NativeSelectOption value="">
                {locale === "zh-CN" ? "未绑定" : "Unbound"}
              </NativeSelectOption>
              {selectedCredentialId && !selectedCredentialKnown ? (
                <NativeSelectOption value={selectedCredentialId} disabled>
                  {locale === "zh-CN"
                    ? `无效密钥：${selectedCredentialId}`
                    : `Invalid key: ${selectedCredentialId}`}
                </NativeSelectOption>
              ) : null}
              {credentialOptions.length ? (
                credentialOptions.map((item) => (
                  <NativeSelectOption key={item.id} value={item.id}>
                    {item.display_name}
                  </NativeSelectOption>
                ))
              ) : null}
            </NativeSelect>
          </Field>
          <div className="flex h-8 w-8 items-center justify-center xl:self-end">
            <SwitchButton
              checked={combo.enabled}
              onChange={(checked) =>
                onUpdateCombo(comboIndex, { enabled: checked })
              }
            />
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2 xl:col-start-5 xl:row-start-1 xl:self-end">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="text-muted-foreground"
              onClick={() => onOpenAdvanced(comboIndex)}
            >
              <Ellipsis size={16} />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="text-destructive hover:text-destructive"
              onClick={() => onRemoveCombo(comboIndex)}
            >
              <X size={16} />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="default"
              className="text-muted-foreground hover:text-foreground"
              onClick={() =>
                onUpdateCombo(comboIndex, {
                  expanded: !combo.expanded,
                })
              }
            >
              <span>{locale === "zh-CN" ? "模型列表" : "Models"}</span>
              <ChevronDown
                size={16}
                className={cn(
                  "transition-transform",
                  combo.expanded ? "rotate-180" : "",
                )}
              />
            </Button>
          </div>
        </div>

        {comboDuplicated ? (
          <div className="text-sm text-destructive">
            {locale === "zh-CN"
              ? "地址来源和密钥重复"
              : "Duplicate Base URL and key"}
          </div>
        ) : null}

        {combo.expanded ? (
          <div className="grid gap-3 pt-1">
            <Separator />
            <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <FieldGroup className="gap-2">
                <div className="text-sm font-medium text-foreground">
                  {locale === "zh-CN" ? "手动添加模型" : "Add model manually"}
                </div>
                <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "模型名称" : "Model name"}
                    </FieldLabel>
                    <Input
                      className="w-full min-w-0"
                      value={combo.manual_model_name}
                      onChange={(event) =>
                        onUpdateCombo(comboIndex, {
                          manual_model_name: event.target.value,
                        })
                      }
                      onKeyDown={(event) => {
                        if (event.key !== "Enter") return;
                        event.preventDefault();
                        onAddManualModel(comboIndex, selectedCredentialId);
                      }}
                      placeholder={
                        locale === "zh-CN" ? "完整模型名" : "Exact model name"
                      }
                    />
                  </Field>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() =>
                      onAddManualModel(comboIndex, selectedCredentialId)
                    }
                    disabled={
                      !selectedCredentialId ||
                      !combo.manual_model_name.trim()
                    }
                  >
                    <Plus data-icon="inline-start" />
                    {locale === "zh-CN" ? "添加模型" : "Add model"}
                  </Button>
                </div>
              </FieldGroup>
              <FieldGroup className="gap-2">
                <div className="text-sm font-medium text-foreground">
                  {locale === "zh-CN"
                    ? "从上游获取模型"
                    : "Fetch upstream models"}
                </div>
                <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "模型过滤" : "Model filter"}
                    </FieldLabel>
                    <Input
                      className="w-full min-w-0"
                      value={combo.match_regex}
                      onChange={(event) =>
                        onUpdateCombo(comboIndex, {
                          match_regex: event.target.value,
                        })
                      }
                      placeholder={
                        locale === "zh-CN"
                          ? "正则表达式，留空获取全部"
                          : "Regex, empty fetches all"
                      }
                    />
                  </Field>
                  <Button
                    type="button"
                    onClick={() => onFetchModels(comboIndex)}
                    disabled={
                      fetchingProtocolIndex === comboIndex ||
                      !form.base_urls.some(
                        (item) => item.enabled && item.url.trim(),
                      ) ||
                      !selectedCredentialActive
                    }
                  >
                    <RefreshCcw
                      data-icon="inline-start"
                      className={
                        fetchingProtocolIndex === comboIndex
                          ? "animate-spin"
                          : ""
                      }
                    />
                    {locale === "zh-CN" ? "获取模型" : "Fetch models"}
                  </Button>
                </div>
              </FieldGroup>
            </div>

            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-medium text-foreground">
                {locale === "zh-CN" ? "已选模型" : "Selected models"}
              </div>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => onUpdateCombo(comboIndex, { models: [] })}
                disabled={!visibleModels.length}
              >
                <Trash2 data-icon="inline-start" />
                {locale === "zh-CN" ? "清空全部" : "Clear all"}
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              {visibleModels.length ? (
                <div className="flex w-full flex-col gap-1.5">
                  {visibleModels.map(({ model, modelIndex }) => (
                    <div
                      key={
                        model.id ||
                        `${model.credential_id}-${model.model_name}-${modelIndex}`
                      }
                      className={cn(
                        "flex min-w-0 items-center gap-2 rounded-md border px-2.5 py-1.5",
                        model.enabled
                          ? "border-border bg-background"
                          : "border-muted bg-muted/30 opacity-65",
                      )}
                    >
                      <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                        {model.model_name}
                      </span>
                      {model.protocol ? (
                        <Badge
                          variant="outline"
                          className={cn(
                            "max-w-[140px] truncate",
                            protocolBadgeClassName(model.protocol),
                          )}
                        >
                          {compactProtocolLabel(model.protocol)}
                        </Badge>
                      ) : null}
                      <Badge variant="secondary" className="max-w-[140px] truncate">
                        {credentialLabelsById.get(model.credential_id) ||
                          model.credential_id}
                      </Badge>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-muted-foreground hover:text-foreground"
                        onClick={() =>
                          onOpenModelTest(comboIndex, modelIndex)
                        }
                        disabled={
                          !model.model_name.trim() ||
                          !activeBaseUrlValue(form, combo).trim() ||
                          !form.credentials.some(
                            (item) =>
                              item.id === model.credential_id &&
                              item.api_key.trim(),
                          )
                        }
                      >
                        {locale === "zh-CN" ? "测试" : "Test"}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-destructive"
                        onClick={() =>
                          onUpdateCombo(comboIndex, {
                            models: combo.models.filter(
                              (_, currentIndex) => currentIndex !== modelIndex,
                            ),
                          })
                        }
                      >
                        <X size={14} />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  {locale === "zh-CN" ? "当前没有模型" : "No models selected"}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function AdvancedProtocolDialog({
  open,
  protocol,
  protocolIndex,
  locale,
  onOpenChange,
  onUpdateProtocol,
  onUpdateProtocolHeader,
}: {
  open: boolean;
  protocol: FormCombo | undefined;
  protocolIndex: number | null;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onUpdateProtocol: (index: number, patch: Partial<FormCombo>) => void;
  onUpdateProtocolHeader: (
    protocolIndex: number,
    headerIndex: number,
    patch: Partial<HeaderItem>,
  ) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {protocolIndex !== null && protocol ? (
        <AppDialogContent
          className="max-w-3xl"
          title={locale === "zh-CN" ? "更多设置" : "More settings"}
        >
          <div className="grid gap-4">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="protocol-proxy">
                  {locale === "zh-CN" ? "代理地址" : "Proxy"}
                </FieldLabel>
                <Input
                  id="protocol-proxy"
                  value={protocol.channel_proxy}
                  onChange={(event) =>
                    onUpdateProtocol(protocolIndex, {
                      channel_proxy: event.target.value,
                    })
                  }
                  placeholder="http://127.0.0.1:7890"
                />
              </Field>
            </FieldGroup>
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-foreground">
                  {locale === "zh-CN" ? "请求头" : "Headers"}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    onUpdateProtocol(protocolIndex, {
                      headers: [...protocol.headers, { key: "", value: "" }],
                    })
                  }
                >
                  <Plus data-icon="inline-start" />
                  {locale === "zh-CN" ? "添加" : "Add"}
                </Button>
              </div>
              {protocol.headers.map((header, headerIndex) => (
                <div
                  key={headerIndex}
                  className="grid gap-3 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
                >
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "请求头名称" : "Header key"}
                    </FieldLabel>
                    <Input
                      value={header.key}
                      onChange={(event) =>
                        onUpdateProtocolHeader(protocolIndex, headerIndex, {
                          key: event.target.value,
                        })
                      }
                      placeholder={
                        locale === "zh-CN" ? "请求头名称" : "Header-Key"
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "请求头值" : "Header value"}
                    </FieldLabel>
                    <Input
                      value={header.value}
                      onChange={(event) =>
                        onUpdateProtocolHeader(protocolIndex, headerIndex, {
                          value: event.target.value,
                        })
                      }
                      placeholder={
                        locale === "zh-CN" ? "请求头值" : "Header-Value"
                      }
                    />
                  </Field>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="text-muted-foreground"
                    onClick={() =>
                      onUpdateProtocol(protocolIndex, {
                        headers:
                          protocol.headers.length > 1
                            ? protocol.headers.filter(
                                (_, currentIndex) =>
                                  currentIndex !== headerIndex,
                              )
                            : protocol.headers,
                      })
                    }
                  >
                    <X size={16} />
                  </Button>
                </div>
              ))}
            </div>
            <Field>
              <FieldLabel htmlFor="protocol-param-override">
                {locale === "zh-CN" ? "参数覆盖" : "Param Override"}
              </FieldLabel>
              <Textarea
                id="protocol-param-override"
                className="min-h-24"
                value={protocol.param_override}
                onChange={(event) =>
                  onUpdateProtocol(protocolIndex, {
                    param_override: event.target.value,
                  })
                }
              />
              <FieldDescription>
                {locale === "zh-CN"
                  ? "填写 JSON 片段用于覆盖请求参数。"
                  : "Use a JSON snippet to override request params."}
              </FieldDescription>
            </Field>
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}

function ModelTestDialog({
  target,
  form,
  locale,
  modelTestPrompts,
  modelTestPromptMode,
  modelTestPrompt,
  modelTestResult,
  testingModel,
  onClose,
  onPromptModeChange,
  onPromptChange,
  onRun,
}: {
  target: ModelTestTarget | null;
  form: FormState;
  locale: Locale;
  modelTestPrompts: string[];
  modelTestPromptMode: string;
  modelTestPrompt: string;
  modelTestResult: SiteModelTestResult | null;
  testingModel: boolean;
  onClose: () => void;
  onPromptModeChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onRun: () => void;
}) {
  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      {target !== null
        ? (() => {
            const protocol = form.combos[target.protocolIndex];
            const model = protocol?.models[target.modelIndex];
            const credentialIndex = model
              ? form.credentials.findIndex(
                  (item) => item.id === model.credential_id,
                )
              : -1;
            const credential =
              credentialIndex >= 0
                ? form.credentials[credentialIndex]
                : undefined;
            const activeBaseUrl = protocol
              ? activeBaseUrlValue(form, protocol).trim()
              : "";
            const canTest = Boolean(
              protocol &&
              model?.model_name.trim() &&
              credential?.api_key.trim() &&
              activeBaseUrl &&
              modelTestPrompt.trim(),
            );
            const sourceText = [
              model?.model_name || "",
              credential
                ? credentialLabel(credential, credentialIndex, locale)
                : "",
              activeBaseUrl,
            ]
              .filter(Boolean)
              .join(" · ");
            return (
              <AppDialogContent
                className="max-w-2xl"
                title={locale === "zh-CN" ? "测试模型" : "Test model"}
              >
                <div className="grid gap-4">
                  <div className="rounded-md border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
                    <div className="truncate text-foreground">
                      {model?.model_name || "-"}
                    </div>
                    <div className="mt-1 break-all text-xs">{sourceText}</div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-[180px_minmax(0,1fr)]">
                    <Field>
                      <FieldLabel>
                        {locale === "zh-CN" ? "问题" : "Prompt"}
                      </FieldLabel>
                      <NativeSelect
                        className={selectClassName()}
                        value={modelTestPromptMode}
                        onChange={(event) =>
                          onPromptModeChange(event.target.value)
                        }
                      >
                        {modelTestPrompts.map((_, index) => (
                          <NativeSelectOption key={index} value={String(index)}>
                            {locale === "zh-CN"
                              ? `预设 ${index + 1}`
                              : `Preset ${index + 1}`}
                          </NativeSelectOption>
                        ))}
                        <NativeSelectOption value="custom">
                          {locale === "zh-CN" ? "自定义" : "Custom"}
                        </NativeSelectOption>
                      </NativeSelect>
                    </Field>
                    <Field>
                      <FieldLabel>
                        {locale === "zh-CN" ? "内容" : "Content"}
                      </FieldLabel>
                      <Textarea
                        className="min-h-24"
                        value={modelTestPrompt}
                        onChange={(event) => onPromptChange(event.target.value)}
                      />
                      {false ? (
                        <p className="mt-1 text-xs text-muted-foreground">
                          {locale === "zh-CN"
                            ? "Rerank 测试：首行为查询，其余行作为候选文档（每行一个）。"
                            : "Rerank test: first line is the query, remaining lines are candidate documents (one per line)."}
                        </p>
                      ) : null}
                    </Field>
                  </div>

                  {modelTestResult ? (
                    <div
                      className={cn(
                        "grid gap-2 rounded-md border px-3 py-2 text-sm",
                        modelTestResult.success
                          ? "bg-muted/20"
                          : "border-destructive/40 bg-destructive/5",
                      )}
                    >
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <Badge
                          variant="outline"
                          className={
                            modelTestResult.success
                              ? "border-primary/30 text-primary"
                              : "border-destructive/40 text-destructive"
                          }
                        >
                          {modelTestResult.success
                            ? locale === "zh-CN"
                              ? "成功"
                              : "Success"
                            : locale === "zh-CN"
                              ? "失败"
                              : "Failed"}
                        </Badge>
                        <span>HTTP {modelTestResult.status_code ?? "-"}</span>
                        <span>{modelTestResult.latency_ms}ms</span>
                      </div>
                      <div
                        className={cn(
                          "max-h-56 overflow-y-auto whitespace-pre-wrap break-words text-sm",
                          modelTestResult.success
                            ? "text-foreground"
                            : "text-destructive",
                        )}
                      >
                        {modelTestResult.success
                          ? modelTestResult.output_text ||
                            (locale === "zh-CN"
                              ? "上游返回成功，但没有可展示文本"
                              : "Upstream succeeded but returned no displayable text")
                          : modelTestResult.error_message ||
                            (locale === "zh-CN" ? "测试失败" : "Test failed")}
                      </div>
                    </div>
                  ) : null}

                  <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={onClose}
                      disabled={testingModel}
                    >
                      {locale === "zh-CN" ? "关闭" : "Close"}
                    </Button>
                    <Button
                      type="button"
                      onClick={onRun}
                      disabled={!canTest || testingModel}
                    >
                      <RefreshCcw
                        data-icon="inline-start"
                        className={testingModel ? "animate-spin" : ""}
                      />
                      {locale === "zh-CN" ? "发送测试" : "Send test"}
                    </Button>
                  </div>
                </div>
              </AppDialogContent>
            );
          })()
        : null}
    </Dialog>
  );
}

function ModelPickerDialog({
  open,
  availableModels,
  pickerSelectedModelKeys,
  locale,
  onOpenChange,
  onToggleModel,
  onConfirm,
  onConfirmAll,
  onCancel,
}: {
  open: boolean;
  availableModels: PickerModelItem[];
  pickerSelectedModelKeys: string[];
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onToggleModel: (key: string) => void;
  onConfirm: () => void;
  onConfirmAll: () => void;
  onCancel: () => void;
}) {
  const modelGroups = useMemo(
    () => groupPickerModels(availableModels),
    [availableModels],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <AppDialogContent
          className="max-w-3xl"
          title={locale === "zh-CN" ? "选择模型" : "Select models"}
        >
          <div className="grid gap-4">
            <div className="max-h-[58dvh] overflow-y-auto p-1 sm:max-h-[420px]">
              <div className="flex flex-wrap gap-2.5">
                {modelGroups.length ? (
                  modelGroups.map((model) => {
                    const key = pickerModelKey(model);
                    const checked = pickerSelectedModelKeys.includes(key);
                    return (
                      <Button
                        key={key}
                        type="button"
                        variant="outline"
                        size="sm"
                        className={cn(
                          "max-w-full rounded-full",
                          modelBadgeClassName(checked),
                          checked ? "border-primary text-primary" : "",
                        )}
                        onClick={() => onToggleModel(key)}
                      >
                        <span className="max-w-[180px] truncate sm:max-w-[220px]">
                          {model.model_name}
                        </span>
                        {model.protocols.map((protocol) => (
                          <Badge
                            key={protocol}
                            variant="outline"
                            className={cn(
                              "text-xs",
                              protocolBadgeClassName(protocol),
                            )}
                          >
                            {compactProtocolLabel(protocol)}
                          </Badge>
                        ))}
                        <span className="text-xs">{checked ? "✓" : "+"}</span>
                      </Button>
                    );
                  })
                ) : (
                  <div className="px-3 py-6 text-sm text-muted-foreground">
                    {locale === "zh-CN"
                      ? "未获取到可选模型"
                      : "No models fetched."}
                  </div>
                )}
              </div>
            </div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button type="button" variant="outline" onClick={onCancel}>
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={onConfirmAll}
                disabled={!modelGroups.length}
              >
                {locale === "zh-CN" ? "加入全部模型" : "Add all models"}
              </Button>
              <Button
                type="button"
                onClick={onConfirm}
                disabled={!pickerSelectedModelKeys.length}
              >
                {locale === "zh-CN" ? "加入模型" : "Add models"}
              </Button>
            </div>
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}

type AggregatedModel = {
  modelName: string;
  protocols: ProtocolKind[];
  sources: string[];
};

function useAggregatedModels(
  combos: FormCombo[],
  baseUrls: FormBaseUrl[],
  locale: Locale,
): AggregatedModel[] {
  return useMemo(() => {
    const aggregate: Record<string, { protocols: Set<ProtocolKind>; sources: Set<string> }> = {};
    combos.forEach((combo, index) => {
      if (!combo.enabled) return;
      const baseUrl = baseUrls.find((b) => b.id === combo.base_url_id);
      if (!baseUrl || !baseUrl.compatible_protocols.length) return;
      const comboName = comboDisplayName(combo, index, locale);
      combo.models.forEach((model) => {
        if (!aggregate[model.model_name]) {
          aggregate[model.model_name] = { protocols: new Set(), sources: new Set() };
        }
        const modelProtocols = model.protocol
          ? [model.protocol]
          : baseUrl.compatible_protocols;
        modelProtocols.forEach((p) =>
          aggregate[model.model_name].protocols.add(p),
        );
        aggregate[model.model_name].sources.add(comboName);
      });
    });
    return Object.entries(aggregate).map(([modelName, { protocols, sources }]) => ({
      modelName,
      protocols: Array.from(protocols),
      sources: Array.from(sources),
    }));
  }, [baseUrls, combos, locale]);
}

function SiteModelAggregateView({
  combos,
  baseUrls,
  locale,
}: {
  combos: FormCombo[];
  baseUrls: FormBaseUrl[];
  locale: Locale;
}) {
  const models = useAggregatedModels(combos, baseUrls, locale);
  if (!models.length) {
    return (
      <div className="py-4 text-sm text-muted-foreground">
        {locale === "zh-CN"
          ? "暂无模型，请先配置地址协议并获取模型"
          : "No models yet. Configure address protocols and fetch models first."}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      {models.map(({ modelName, protocols, sources }) => (
        <div
          key={modelName}
          className="flex min-w-0 flex-wrap items-center gap-2 rounded-md border bg-background px-3 py-2"
        >
          <span className="min-w-0 flex-1 truncate text-sm font-medium">{modelName}</span>
          <div className="flex flex-wrap gap-1">
            {protocols.map((p) => (
              <Badge
                key={p}
                variant="outline"
                className={cn("text-xs", protocolBadgeClassName(p))}
              >
                {compactProtocolLabel(p)}
              </Badge>
            ))}
          </div>
          <span className="text-xs text-muted-foreground">{sources.join(", ")}</span>
        </div>
      ))}
    </div>
  );
}

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
  const [deleteTarget, setDeleteTarget] = useState<Site | null>(null);
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(() => emptyForm(locale));
  const [newComboName, setNewComboName] = useState("");
  const [comboNameDialogOpen, setComboNameDialogOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [fetchingProtocolIndex, setFetchingProtocolIndex] = useState<
    number | null
  >(null);
  const [advancedProtocolIndex, setAdvancedProtocolIndex] = useState<
    number | null
  >(null);
  const [modelPickerProtocolIndex, setModelPickerProtocolIndex] = useState<
    number | null
  >(null);
  const [availableModels, setAvailableModels] = useState<PickerModelItem[]>([]);
  const [pickerSelectedModelKeys, setPickerSelectedModelKeys] = useState<
    string[]
  >([]);
  const [modelTestTarget, setModelTestTarget] =
    useState<ModelTestTarget | null>(null);
  const [modelTestPromptMode, setModelTestPromptMode] = useState("0");
  const [modelTestPrompt, setModelTestPrompt] = useState("");
  const [modelTestResult, setModelTestResult] =
    useState<SiteModelTestResult | null>(null);
  const [testingModel, setTestingModel] = useState(false);
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
  const {
    data: siteRuntimeSummaries,
  } = useQuery({
    queryKey: ["site-runtime-summaries"],
    queryFn: () => apiRequest<SiteRuntimeSummary[]>("/admin/sites/runtime"),
    staleTime: 5_000,
    refetchInterval: 5000,
  });
  const {
    data: routerSnapshot,
  } = useQuery({
    queryKey: ["router-snapshot"],
    queryFn: () => apiRequest<RouteSnapshot>("/admin/routes"),
    staleTime: 5_000,
    refetchInterval: 5000,
  });
  const {
    data: settings,
  } = useQuery({
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
  const siteRows = useMemo<SiteRow[]>(
    () =>
      (sites ?? []).map((site) => ({
        ...site,
        subtitle: siteSubtitle(site),
        protocol_count: site.protocols.filter((p) => p.enabled).length,
        credential_count: site.credentials.length,
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
        !site.base_urls.some((b) => b.compatible_protocols.includes(protocolFilter))
      )
        return false;
      if (!keyword) return true;
      const stack = [
        site.name,
        site.subtitle,
        site.endpoint_summary,
        ...site.protocols.flatMap((item) =>
          item.models.map((model) => model.model_name),
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
          right.protocol_count - left.protocol_count ||
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
  const submittedBaseUrls = useMemo(
    () => formBaseUrlsForPayload(form),
    [form],
  );
  const duplicatedComboKeys = useMemo(
    () =>
      duplicateComboKeys(
        form.combos,
        submittedBaseUrls,
      ),
    [form.combos, submittedBaseUrls],
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

  function openCreate() {
    if (!confirmDiscardChanges()) return;
    setEditingSiteId(null);
    applyPreparedForm(emptyForm(locale));
    setDialogOpen(true);
  }

  function openEdit(site: Site) {
    if (!confirmDiscardChanges()) return;
    setEditingSiteId(site.id);
    applyPreparedForm(toForm(site, locale));
    setDialogOpen(true);
  }

  function closeEditor() {
    if (!confirmDiscardChanges()) return;
    setDialogOpen(false);
    setEditingSiteId(null);
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
          ? "协议地址来源无效"
          : "Protocol Base URL is invalid",
      );
      return;
    }
    if (duplicatedComboKeys.size) {
      const message =
        locale === "zh-CN"
          ? "同一个渠道内不允许重复地址来源和密钥"
          : "Duplicate Base URL and key pairs are not allowed in one channel";
      toast.error(message);
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
            compatible_protocols: item.compatible_protocols ?? [],
          })),
          credentials: site.credentials.map((item) => ({
            id: item.id,
            name: item.name,
            api_key: item.api_key,
            enabled: item.enabled,
          })),
          protocols: site.protocols.map((item) => ({
            id: item.id,
            name: item.name,
            enabled,
            headers: item.headers,
            channel_proxy: item.channel_proxy,
            param_override: item.param_override,
            match_regex: item.match_regex,
            base_url_id: item.base_url_id,
            credential_id: item.credential_id,
            models: item.models.map((model) => ({
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
        combos: current.combos.map((combo) => {
          const credentialId =
            combo.credential_id === target.id ? "" : combo.credential_id;
          return {
            ...combo,
            credential_id: credentialId,
            models: combo.models.filter(
              (model) => model.credential_id !== target.id,
            ),
          };
        }),
      };
    });
  }

  function updateCombo(index: number, patch: Partial<FormCombo>) {
    setForm((current) => ({
      ...current,
      combos: current.combos.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  }

  function openAddComboDialog() {
    setNewComboName(nextComboName(form.combos, locale));
    setComboNameDialogOpen(true);
  }

  function addComboWithName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newComboName.trim();
    if (!name) {
      toast.error(locale === "zh-CN" ? "请输入组合名称" : "Enter a combo name");
      return;
    }
    const exists = form.combos.some(
      (combo, index) =>
        comboDisplayName(combo, index, locale).toLowerCase() === name.toLowerCase(),
    );
    if (exists) {
      toast.error(
        locale === "zh-CN"
          ? "组合名称已存在"
          : "Combo name already exists",
      );
      return;
    }
    setForm((current) => ({
      ...current,
      combos: [
        ...current.combos,
        {
          ...emptyCombo(defaultBaseUrlId(current.base_urls), name),
        },
      ],
    }));
    setComboNameDialogOpen(false);
    setNewComboName("");
  }

  function addBaseUrl() {
    const baseUrl = {
      id: createLocalId("baseurl"),
      url: "",
      name: "",
      enabled: true,
      compatible_protocols: [] as ProtocolKind[],
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
        combos: current.combos.map((combo) => ({
          ...combo,
          base_url_id: resolveBaseUrlId(baseUrls, combo.base_url_id),
        })),
      };
    });
  }

  function updateProtocolHeader(
    protocolIndex: number,
    headerIndex: number,
    patch: Partial<HeaderItem>,
  ) {
    setForm((current) => ({
      ...current,
      combos: current.combos.map((item, itemIndex) =>
        itemIndex !== protocolIndex
          ? item
          : {
              ...item,
              headers: item.headers.map((header, currentHeaderIndex) =>
                currentHeaderIndex === headerIndex
                  ? { ...header, ...patch }
                  : header,
              ),
            },
      ),
    }));
  }

  function addManualProtocolModel(protocolIndex: number, credentialId: string) {
    const protocol = form.combos[protocolIndex];
    const modelName = protocol?.manual_model_name.trim() ?? "";
    if (!protocol || !credentialId || !modelName) return;
    if (
      protocol.models.some(
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
      combos: current.combos.map((item, itemIndex) => {
        if (itemIndex !== protocolIndex) return item;
        return {
          ...item,
          manual_model_name: "",
          expanded: true,
          models: [
            ...item.models,
            {
              id: null,
              credential_id: credentialId,
              model_name: modelName,
              enabled: true,
            },
          ],
        };
      }),
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
    setModelPickerProtocolIndex(null);
    setAvailableModels([]);
    setPickerSelectedModelKeys([]);
  }

  function openModelTest(protocolIndex: number, modelIndex: number) {
    setModelTestTarget({ protocolIndex, modelIndex });
    setModelTestPromptMode("0");
    setModelTestPrompt(modelTestPrompts[0] || "");
    setModelTestResult(null);
  }

  function closeModelTest() {
    if (testingModel) return;
    setModelTestTarget(null);
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
    if (modelPickerProtocolIndex === null) return;
    const selectedModels = availableModels.filter((item) =>
      selectedKeys.includes(pickerModelKey(item)),
    );
    const selectedModelGroups = groupPickerModels(selectedModels);
    setForm((current) => ({
      ...current,
      combos: current.combos.map((item, itemIndex) => {
        if (itemIndex !== modelPickerProtocolIndex) return item;
        const merged = [...item.models];
        const existingModels = new Map(
          merged.map((model, index) => [genericModelKey(model), index]),
        );
        for (const model of selectedModelGroups) {
          const genericKey = genericModelKey(model);
          const existingIndex = existingModels.get(genericKey);
          if (existingIndex !== undefined) {
            const existing = merged[existingIndex];
            merged[existingIndex] = {
              ...existing,
              protocol: mergedModelProtocol(
                existing.protocol,
                model.protocols,
              ),
            };
            continue;
          }
          existingModels.set(genericKey, merged.length);
          merged.push({
            id: null,
            protocol:
              model.protocols.length === 1 ? model.protocols[0] : undefined,
            credential_id: model.credential_id,
            model_name: model.model_name,
            enabled: true,
          });
        }
        return { ...item, models: merged, expanded: true };
      }),
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

  async function fetchProtocolModels(protocolIndex: number) {
    const combo = form.combos[protocolIndex];
    if (!combo) return;
    const selectedCredentialId = effectiveProtocolCredentialId(
      combo,
      form.credentials,
    );
    if (!selectedCredentialId) {
      toast.error(locale === "zh-CN" ? "组合密钥无效" : "Combo key is invalid");
      return;
    }
    setFetchingProtocolIndex(protocolIndex);
    try {
      const activeBaseUrl = activeBaseUrlValue(form, combo);
      const compatibleProtocols =
        form.base_urls.find((b) => b.id === combo.base_url_id)?.compatible_protocols ?? [];
      const payload: SiteModelFetchPayload = {
        compatible_protocols: compatibleProtocols,
        base_url: safeText(activeBaseUrl).trim(),
        headers: formHeaders(combo),
        channel_proxy: combo.channel_proxy.trim(),
        match_regex: safeText(combo.match_regex).trim(),
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
        protocol: item.protocol,
        credential_id: item.credential_id,
        model_name: item.model_name,
      }));
      setAvailableModels(nextAvailableModels);
      setPickerSelectedModelKeys([]);
      setModelPickerProtocolIndex(protocolIndex);
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
      setFetchingProtocolIndex(null);
    }
  }

  async function runModelTest() {
    if (!modelTestTarget) return;
    const protocol = form.combos[modelTestTarget.protocolIndex];
    const model = protocol?.models[modelTestTarget.modelIndex];
    const credentialIndex = model
      ? form.credentials.findIndex((item) => item.id === model.credential_id)
      : -1;
    const credential =
      credentialIndex >= 0 ? form.credentials[credentialIndex] : undefined;
    const prompt = modelTestPrompt.trim();
    const activeBaseUrl = protocol
      ? activeBaseUrlValue(form, protocol).trim()
      : "";
    if (
      !protocol ||
      !model ||
      !credential ||
      !credential.api_key.trim() ||
      !activeBaseUrl ||
      !prompt
    ) {
      toast.error(
        locale === "zh-CN"
          ? "测试参数不完整"
          : "Test parameters are incomplete",
      );
      return;
    }
    const baseUrlProtocols =
      form.base_urls.find((b) => b.id === protocol.base_url_id)?.compatible_protocols ?? [];
    const payload: SiteModelTestPayload = {
      protocol: model.protocol ?? baseUrlProtocols[0] ?? "openai_chat",
      base_url: activeBaseUrl,
      headers: formHeaders(protocol),
      channel_proxy: protocol.channel_proxy.trim(),
      param_override: protocol.param_override.trim(),
      credential: {
        id: credential.id,
        name: credential.name.trim() || fallbackCredentialName(credentialIndex),
        api_key: credential.api_key.trim(),
      },
      model_name: model.model_name.trim(),
      prompt,
    };
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

  return (
    <TooltipProvider>
      <section className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-xl font-semibold text-foreground">
            {locale === "zh-CN" ? "渠道" : "Channels"}
          </h1>
          <Button
            type="button"
            onClick={openCreate}
            className="rounded-full"
            size="icon-sm"
            title={locale === "zh-CN" ? "新建渠道" : "New channel"}
          >
            <Plus size={18} />
          </Button>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_320px]">
          <Card className="overflow-hidden py-0 xl:min-h-[calc(100dvh-12rem)]">
            <CardContent className="px-3 py-3 xl:max-h-[calc(100dvh-12rem)] xl:overflow-y-auto">
              {isLoading ? (
                <div className="px-2 py-6 text-sm text-muted-foreground">
                  {locale === "zh-CN"
                    ? "正在加载渠道..."
                    : "Loading channels..."}
                </div>
              ) : sitesIsError ? null : visibleSites.length ? (
                <ItemGroup className="gap-3">
                  {visibleSites.map((site) => {
                    const runtimeSummary = siteRuntimeById.get(site.id);
                    return (
                      <Item
                        key={site.id}
                        variant="outline"
                        role="button"
                        tabIndex={0}
                        className="items-start gap-3 rounded-2xl border-border/80 bg-gradient-to-r from-background to-muted/[0.18] px-4 py-4 shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer sm:gap-4 sm:px-5 sm:py-5"
                        onClick={() => openEdit(site)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            openEdit(site);
                          }
                        }}
                      >
                        <ItemMedia
                          variant="icon"
                          className="mt-0.5 hidden self-start sm:flex"
                        >
                          <SiteFavicon
                            key={site.endpoint_summary}
                            url={site.endpoint_summary}
                            name={site.name}
                          />
                        </ItemMedia>
                        <ItemContent className="min-w-0">
                          <div className="flex flex-col gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <ItemTitle className="truncate text-base">
                                {site.name}
                              </ItemTitle>
                              {Array.from(
                                new Set(site.base_urls.flatMap((b) => b.compatible_protocols)),
                              ).map((p) => (
                                <Badge
                                  key={p}
                                  variant="outline"
                                  className={cn(
                                    "px-2.5 py-0.5",
                                    protocolBadgeClassName(p),
                                  )}
                                >
                                  {protocolLabel(p)}
                                </Badge>
                              ))}
                            </div>
                            <ItemDescription className="truncate text-sm">
                              {site.endpoint_summary ||
                                (locale === "zh-CN"
                                  ? "未配置请求地址"
                                  : "No endpoint configured")}
                            </ItemDescription>
                            <SiteHealthPreview
                              site={site}
                              summary={runtimeSummary}
                              healthByChannelId={channelHealthById}
                              locale={locale}
                              timeZone={timeZone}
                            />
                          </div>
                          <ItemFooter className="mt-4 flex flex-wrap items-center gap-2.5">
                            <ChannelMetric
                              icon={<Activity size={14} />}
                              label={locale === "zh-CN" ? "请求数" : "Requests"}
                              value={String(
                                runtimeSummary?.recent_request_count ?? 0,
                              )}
                            />
                            <ChannelMetric
                              icon={<Waypoints size={14} />}
                              label={locale === "zh-CN" ? "协议" : "Protocols"}
                              value={String(site.protocol_count)}
                            />
                            <ChannelMetric
                              icon={<Server size={14} />}
                              label={locale === "zh-CN" ? "模型" : "Models"}
                              value={String(site.model_count)}
                            />
                            <ChannelMetric
                              icon={<KeyRound size={14} />}
                              label={locale === "zh-CN" ? "密钥" : "Keys"}
                              value={String(site.credential_count)}
                            />
                          </ItemFooter>
                        </ItemContent>
                        <ItemActions
                          className="basis-full flex-wrap justify-end self-start sm:ml-auto sm:basis-auto sm:shrink-0"
                          onClick={(event) => event.stopPropagation()}
                          onKeyDown={(event) => event.stopPropagation()}
                        >
                          <SwitchButton
                            checked={isSiteEnabled(site)}
                            disabled={busyId === site.id}
                            onChange={(checked) =>
                              void toggleSiteEnabled(site, checked)
                            }
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="rounded-full text-destructive hover:text-destructive"
                            onClick={() => setDeleteTarget(site)}
                          >
                            <Trash2 data-icon="inline-start" />
                            {locale === "zh-CN" ? "删除" : "Delete"}
                          </Button>
                        </ItemActions>
                      </Item>
                    );
                  })}
                </ItemGroup>
              ) : (
                <div className="rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">
                  {search.trim()
                    ? locale === "zh-CN"
                      ? "没有匹配的渠道。"
                      : "No matching channels."
                    : locale === "zh-CN"
                      ? "当前还没有渠道。"
                      : "No channels yet."}
                </div>
              )}
            </CardContent>
          </Card>

          <aside className="order-1 xl:order-2">
            <ChannelFiltersPanel
              locale={locale}
              search={search}
              statusFilter={statusFilter}
              protocolFilter={protocolFilter}
              sortBy={sortBy}
              activeFilterCount={activeFilterCount}
              onSearchChange={setSearch}
              onStatusChange={setStatusFilter}
              onProtocolChange={setProtocolFilter}
              onSortChange={setSortBy}
              onReset={resetFilters}
            />
          </aside>
        </div>
        <Dialog
          open={dialogOpen}
          onOpenChange={(open) => {
            if (!open && hasUnsavedChanges) {
              const confirmed = window.confirm(
                locale === "zh-CN"
                  ? "当前有未保存修改，确定关闭吗？"
                  : "You have unsaved changes. Close anyway?",
              );
              if (!confirmed) return;
            }
            setDialogOpen(open);
            if (!open) {
              setEditingSiteId(null);
            }
          }}
        >
          <AppDialogContent
            className="max-w-4xl"
            title={
              editingSiteId
                ? locale === "zh-CN"
                  ? "编辑渠道"
                  : "Edit channel"
                : locale === "zh-CN"
                  ? "新建渠道"
                  : "Create channel"
            }
          >
            <form className="grid gap-5" onSubmit={submit}>
              <div className="grid gap-4">
                <section className="grid gap-5">
                  <div className="text-base font-semibold text-foreground">
                    {locale === "zh-CN" ? "基本信息" : "Channel and keys"}
                  </div>
                  <FieldGroup className="gap-4">
                    <Field>
                      <FieldLabel htmlFor="channel-name">
                        {locale === "zh-CN" ? "渠道名称" : "Channel name"}
                      </FieldLabel>
                      <Input
                        id="channel-name"
                        value={form.name}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            name: event.target.value,
                          }))
                        }
                      />
                    </Field>

                    <div className="grid gap-4 xl:grid-cols-2">
                      <section className="grid gap-3">
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <div className="text-sm font-medium text-foreground">
                            {locale === "zh-CN" ? "请求地址" : "Base URLs"}
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={addBaseUrl}
                          >
                            <Plus data-icon="inline-start" />
                            {locale === "zh-CN" ? "添加" : "Add"}
                          </Button>
                        </div>
                        <FieldGroup className="gap-3">
                          {form.base_urls.map((baseUrl, index) => (
                            <div
                              key={baseUrl.id}
                              className="grid min-w-0 gap-3 border-b pb-3 last:border-b-0 last:pb-0"
                            >
                              <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1.65fr)_minmax(0,0.85fr)_32px_32px] md:items-end">
                                <FieldGroup className="min-w-0 gap-3 md:contents">
                                  <Field>
                                    <FieldLabel>
                                      {baseUrlIndexLabel(index, locale)}
                                    </FieldLabel>
                                    <Input
                                      className="w-full min-w-0"
                                      value={baseUrl.url}
                                      onChange={(event) =>
                                        updateBaseUrl(index, {
                                          url: event.target.value,
                                        })
                                      }
                                      placeholder="https://api.example.com"
                                    />
                                  </Field>
                                  <Field>
                                    <FieldLabel>
                                      {locale === "zh-CN" ? "备注" : "Remark"}
                                    </FieldLabel>
                                    <Input
                                      className="w-full min-w-0"
                                      value={baseUrl.name}
                                      onChange={(event) =>
                                        updateBaseUrl(index, {
                                          name: event.target.value,
                                        })
                                      }
                                      placeholder={
                                        locale === "zh-CN" ? "备注" : "Remark"
                                      }
                                    />
                                  </Field>
                                  <div className="flex h-8 w-8 items-center justify-center">
                                    <SwitchButton
                                      checked={baseUrl.enabled}
                                      onChange={(checked) =>
                                        updateBaseUrl(index, { enabled: checked })
                                      }
                                    />
                                  </div>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="icon"
                                    className="text-muted-foreground"
                                    onClick={() => removeBaseUrl(index)}
                                    disabled={form.base_urls.length <= 1}
                                  >
                                    <X size={16} />
                                  </Button>
                                </FieldGroup>
                              </div>
                              <div>
                                <div className="mb-1.5 text-xs font-medium text-muted-foreground">
                                  {locale === "zh-CN" ? "兼容协议" : "Compatible Protocols"}
                                </div>
                                <ToggleGroup
                                  type="multiple"
                                  value={baseUrl.compatible_protocols}
                                  onValueChange={(vals) =>
                                    updateBaseUrl(index, { compatible_protocols: vals as ProtocolKind[] })
                                  }
                                  className="flex flex-wrap justify-start gap-1"
                                >
                                  {protocolOptions.map((opt) => (
                                    <ToggleGroupItem
                                      key={opt.value}
                                      value={opt.value}
                                      className="h-7 px-3 text-xs rounded-full border data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
                                    >
                                      {compactProtocolLabel(opt.value)}
                                    </ToggleGroupItem>
                                  ))}
                                </ToggleGroup>
                              </div>
                            </div>
                          ))}
                        </FieldGroup>
                      </section>

                      <section className="grid gap-3">
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <div className="text-sm font-medium text-foreground">
                            {locale === "zh-CN" ? "密钥" : "API Keys"}
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              setForm((current) => ({
                                ...current,
                                credentials: [
                                  ...current.credentials,
                                  {
                                    id: createLocalId("credential"),
                                    name: "",
                                    api_key: "",
                                    enabled: true,
                                  },
                                ],
                              }))
                            }
                          >
                            <Plus data-icon="inline-start" />
                            {locale === "zh-CN" ? "添加" : "Add"}
                          </Button>
                        </div>
                        <FieldGroup className="gap-3">
                          {form.credentials.map((credential, index) => (
                            <div
                              key={credential.id}
                              className="grid min-w-0 gap-3 border-b pb-3 last:border-b-0 last:pb-0 md:grid-cols-[minmax(0,1.65fr)_minmax(0,0.85fr)_32px_32px] md:items-end"
                            >
                              <FieldGroup className="min-w-0 gap-3 md:contents">
                                <Field>
                                  <FieldLabel>
                                    {credentialIndexLabel(index, locale)}
                                  </FieldLabel>
                                  <Input
                                    className="w-full min-w-0"
                                    value={credential.api_key}
                                    onChange={(event) =>
                                      updateCredential(index, {
                                        api_key: event.target.value,
                                      })
                                    }
                                    placeholder="sk-..."
                                  />
                                </Field>
                                <Field>
                                  <FieldLabel>
                                    {locale === "zh-CN" ? "备注" : "Remark"}
                                  </FieldLabel>
                                  <Input
                                    className="w-full min-w-0"
                                    value={credential.name}
                                    onChange={(event) =>
                                      updateCredential(index, {
                                        name: event.target.value,
                                      })
                                    }
                                    placeholder={
                                      locale === "zh-CN" ? "备注" : "Remark"
                                    }
                                  />
                                </Field>
                                <div className="flex h-8 w-8 items-center justify-center">
                                  <SwitchButton
                                    checked={credential.enabled}
                                    onChange={(checked) =>
                                      updateCredential(index, {
                                        enabled: checked,
                                      })
                                    }
                                  />
                                </div>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="icon"
                                  className="text-muted-foreground"
                                  onClick={() => removeCredential(index)}
                                >
                                  <X size={16} />
                                </Button>
                              </FieldGroup>
                            </div>
                          ))}
                        </FieldGroup>
                      </section>
                    </div>
                  </FieldGroup>
                </section>

                <Separator />

                <section className="grid gap-4">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div className="text-base font-semibold text-foreground">
                      {locale === "zh-CN" ? "组合" : "Combos"}
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      className="justify-start border-dashed"
                      onClick={openAddComboDialog}
                    >
                      <Plus data-icon="inline-start" />
                      {locale === "zh-CN"
                        ? "增加一个组合"
                        : "Add combo"}
                    </Button>
                  </div>
                  <div className="flex flex-col gap-3">
                    {form.combos.map((combo, comboIndex) => (
                      <ComboConfigItem
                        key={combo.id || comboIndex}
                        form={form}
                        combo={combo}
                        comboIndex={comboIndex}
                        locale={locale}
                        fetchingProtocolIndex={fetchingProtocolIndex}
                        duplicatedComboKeys={duplicatedComboKeys}
                        onUpdateCombo={updateCombo}
                        onRemoveCombo={(index) =>
                          setForm((current) => ({
                            ...current,
                            combos:
                              current.combos.length > 1
                                ? current.combos.filter(
                                    (_, currentIndex) => currentIndex !== index,
                                  )
                                : current.combos,
                          }))
                        }
                        onAddManualModel={addManualProtocolModel}
                        onFetchModels={fetchProtocolModels}
                        onOpenAdvanced={setAdvancedProtocolIndex}
                        onOpenModelTest={openModelTest}
                      />
                    ))}
                  </div>
                  <div className="mt-4">
                    <div className="mb-2 text-sm font-medium text-foreground">
                      {locale === "zh-CN" ? "模型总览" : "Model Overview"}
                    </div>
                    <SiteModelAggregateView
                      combos={form.combos}
                      baseUrls={form.base_urls}
                      locale={locale}
                    />
                  </div>
                </section>
              </div>
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
                <Button type="button" variant="outline" onClick={closeEditor}>
                  {locale === "zh-CN" ? "取消" : "Cancel"}
                </Button>
                <Button type="submit">
                  {editingSiteId
                    ? locale === "zh-CN"
                      ? "保存渠道"
                      : "Save channel"
                    : locale === "zh-CN"
                      ? "创建渠道"
                      : "Create channel"}
                </Button>
              </div>
            </form>
          </AppDialogContent>
        </Dialog>
        <Dialog open={comboNameDialogOpen} onOpenChange={setComboNameDialogOpen}>
          <AppDialogContent
            className="max-w-md"
            title={locale === "zh-CN" ? "命名组合" : "Name combo"}
          >
            <form className="grid gap-4" onSubmit={addComboWithName}>
              <Field>
                <FieldLabel htmlFor="new-combo-name">
                  {locale === "zh-CN" ? "组合名称" : "Combo name"}
                </FieldLabel>
                <Input
                  id="new-combo-name"
                  value={newComboName}
                  autoFocus
                  onChange={(event) => setNewComboName(event.target.value)}
                />
              </Field>
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setComboNameDialogOpen(false)}
                >
                  {locale === "zh-CN" ? "取消" : "Cancel"}
                </Button>
                <Button type="submit">
                  {locale === "zh-CN" ? "创建组合" : "Create combo"}
                </Button>
              </div>
            </form>
          </AppDialogContent>
        </Dialog>

        <AdvancedProtocolDialog
          open={advancedProtocolIndex !== null}
          protocol={
            advancedProtocolIndex !== null
              ? form.combos[advancedProtocolIndex]
              : undefined
          }
          protocolIndex={advancedProtocolIndex}
          locale={locale}
          onOpenChange={(open) => {
            if (!open) setAdvancedProtocolIndex(null);
          }}
          onUpdateProtocol={updateCombo}
          onUpdateProtocolHeader={updateProtocolHeader}
        />

        <Dialog
          open={Boolean(deleteTarget)}
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null);
          }}
        >
          <AppDialogContent
            className="max-w-lg"
            title={locale === "zh-CN" ? "确认删除渠道" : "Delete channel"}
            description={
              locale === "zh-CN"
                ? "删除后该渠道下的协议、模型和模型组成员会一起移除。"
                : "Protocol configs, models, and group members under this channel will be removed together."
            }
          >
            <div className="grid gap-5">
              <div className="rounded-md border bg-muted/30 p-4">
                <strong className="text-foreground">
                  {deleteTarget?.name}
                </strong>
                <p className="mt-2 text-xs text-muted-foreground">
                  {deleteTarget ? siteSubtitle(deleteTarget) : ""}
                </p>
              </div>
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDeleteTarget(null)}
                >
                  {locale === "zh-CN" ? "取消" : "Cancel"}
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => deleteTarget && void removeSite(deleteTarget)}
                  disabled={busyId === deleteTarget?.id}
                >
                  {busyId === deleteTarget?.id
                    ? locale === "zh-CN"
                      ? "删除中..."
                      : "Deleting..."
                    : locale === "zh-CN"
                      ? "确认删除"
                      : "Delete"}
                </Button>
              </div>
            </div>
          </AppDialogContent>
        </Dialog>

        <ModelTestDialog
          target={modelTestTarget}
          form={form}
          locale={locale}
          modelTestPrompts={modelTestPrompts}
          modelTestPromptMode={modelTestPromptMode}
          modelTestPrompt={modelTestPrompt}
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
          onRun={() => void runModelTest()}
        />

        <ModelPickerDialog
          open={modelPickerProtocolIndex !== null}
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
      </section>
    </TooltipProvider>
  );
}
