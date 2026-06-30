"use client";

import { useState } from "react";
import { Globe2 } from "lucide-react";
import type {
  ChannelProxyMode,
  ProtocolKind,
  Site,
  SiteBatchImportPayload,
  SiteBatchImportResult,
  SiteBaseUrlInput,
  SiteCredentialInput,
  SiteModelInput,
  SitePayload,
} from "@/lib/api";
import { isGeneratedCredentialName } from "@/lib/utils";
import {
  protocolLabel,
  protocolOptions,
  compactProtocolLabel,
  protocolBadgeClassName,
} from "@/lib/protocols";
export {
  isGeneratedCredentialName,
  protocolBadgeClassName,
  protocolLabel,
  protocolOptions,
  compactProtocolLabel,
};
import type { Locale } from "@/lib/i18n";

export type HeaderItem = { key: string; value: string };
export type FormCredential = Omit<SiteCredentialInput, "id"> & { id: string };
export type FormBaseUrl = Omit<SiteBaseUrlInput, "id"> & {
  id: string;
  supported_protocols: ProtocolKind[];
};
export type { Locale };

export function createLocalId(prefix: string) {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export type FormModel = Omit<SiteModelInput, "protocol"> & {
  protocols: ProtocolKind[];
  protocolIds?: Record<string, string>;
};

export type FormProtocolConfig = {
  id?: string | null;
  name: string;
  enabled: boolean;
  headers: HeaderItem[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  param_override: string;
  match_regex: string;
  manual_model_name: string;
  manual_protocols: ProtocolKind[];
  base_url_id: string;
  credential_id: string;
  auto_sync_enabled: boolean;
  models: FormModel[];
  expanded: boolean;
};

export type FormState = {
  name: string;
  base_urls: FormBaseUrl[];
  credentials: FormCredential[];
  protocolConfigs: FormProtocolConfig[];
};

export type PickerModelItem = {
  credential_id: string;
  credential_name?: string;
  model_name: string;
};

export function genericModelKey(
  model: Pick<PickerModelItem, "credential_id" | "model_name">,
) {
  return `${model.credential_id}:${model.model_name}`;
}

export function protocolConfigModelKey(
  protocolConfigIndex: number,
  protocolConfig: Pick<FormProtocolConfig, "id" | "base_url_id">,
  model: Pick<FormModel, "credential_id" | "model_name">,
) {
  const protocolConfigKey =
    protocolConfig.id?.trim() || `index-${protocolConfigIndex}`;
  return JSON.stringify([
    protocolConfigKey,
    protocolConfig.base_url_id,
    model.credential_id,
    model.model_name,
  ]);
}

export function groupPickerModels(models: PickerModelItem[]) {
  const groups = new Map<string, PickerModelItem>();
  for (const model of models) {
    const key = genericModelKey(model);
    if (groups.has(key)) {
      continue;
    }
    groups.set(key, {
      credential_id: model.credential_id,
      credential_name: model.credential_name,
      model_name: model.model_name,
    });
  }
  return Array.from(groups.values());
}

export function pickerModelKeys(models: PickerModelItem[]) {
  return Array.from(new Set(models.map((item) => genericModelKey(item))));
}

export function modelSupportedProtocols(
  model: Pick<FormModel, "protocols"> | null | undefined,
) {
  if (model?.protocols && model.protocols.length > 0) {
    return Array.from(new Set(model.protocols));
  }
  return [];
}

export function selectedModelTestProtocol(
  protocols: ProtocolKind[],
  selectedProtocol: ProtocolKind | null,
) {
  return selectedProtocol && protocols.includes(selectedProtocol)
    ? selectedProtocol
    : (protocols[0] ?? null);
}

export type ModelTestTarget = {
  protocolConfigIndex: number;
  modelIndex: number;
};

export type BatchModelTestStatus = "pending" | "running" | "success" | "failed";

export type BatchModelTestRow = {
  key: string;
  modelName: string;
  credentialName: string;
  protocol: ProtocolKind;
  status: BatchModelTestStatus;
  statusCode?: number | null;
  latencyMs?: number;
  message: string;
};

export type BatchModelTestOption = {
  key: string;
  target: ModelTestTarget;
  modelName: string;
  credentialName: string;
  protocols: ProtocolKind[];
  selectedProtocol: ProtocolKind;
};

export type TestableModelOption = Omit<
  BatchModelTestOption,
  "selectedProtocol"
>;

export type SiteRow = Site & {
  subtitle: string;
  enabled_protocol_channel_count: number;
  model_count: number;
  endpoint_summary: string;
};

export type ChannelStatusFilter = "all" | "enabled" | "disabled";
export type ChannelSort =
  | "requests-desc"
  | "name-asc"
  | "name-desc"
  | "models-desc"
  | "protocols-desc";

export const emptyProtocolConfig = (
  baseUrlId = "",
  name = "",
  credentialId = "",
): FormProtocolConfig => ({
  id: null,
  name,
  enabled: true,
  headers: [{ key: "", value: "" }],
  proxy_mode: "inherit",
  channel_proxy: "",
  param_override: "",
  match_regex: "",
  manual_model_name: "",
  manual_protocols: [],
  base_url_id: baseUrlId,
  credential_id: credentialId,
  auto_sync_enabled: false,
  models: [],
  expanded: true,
});

export type ImportResultRow = {
  key: string;
  index: number;
  name: string;
  status: "created" | "skipped" | "error";
  reason: string;
};

export const batchImportTemplate: SiteBatchImportPayload = {
  sites: [
    {
      name: "OpenAI",
      base_urls: [
        {
          ref: "main",
          url: "https://api.openai.com/v1",
          name: "",
          enabled: true,
        },
      ],
      credentials: [
        {
          ref: "key1",
          name: "Key 1",
          api_key: "sk-...",
          enabled: true,
        },
      ],
      protocols: [
        {
          protocol: "openai_chat",
          enabled: true,
          base_url_ref: "main",
          credential_ref: "key1",
          headers: {},
          proxy_mode: "inherit",
          channel_proxy: "",
          param_override: "",
          match_regex: "",
          models: [
            {
              model_name: "gpt-4.1",
              credential_ref: "key1",
              enabled: true,
            },
          ],
        },
      ],
    },
  ],
};

export function batchImportTemplateText(): string {
  return JSON.stringify(batchImportTemplate, null, 2);
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function parseBatchImportPayload(
  text: string,
  locale: Locale,
): SiteBatchImportPayload {
  const content = text.trim();
  if (!content) {
    throw new Error(locale === "zh-CN" ? "JSON 内容为空" : "JSON is empty");
  }

  let value: unknown;
  try {
    value = JSON.parse(content);
  } catch {
    throw new Error(
      locale === "zh-CN" ? "JSON 格式无效" : "Invalid JSON format",
    );
  }

  if (!isRecord(value) || !Array.isArray(value.sites)) {
    throw new Error(
      locale === "zh-CN"
        ? "JSON 必须包含 sites 数组"
        : "JSON must include a sites array",
    );
  }

  return value as SiteBatchImportPayload;
}

export function importReasonLabel(reason: string, locale: Locale): string {
  if (reason === "duplicate_name") {
    return locale === "zh-CN" ? "同名渠道已存在" : "Channel already exists";
  }
  if (reason === "duplicate_in_file") {
    return locale === "zh-CN" ? "文件内重名" : "Duplicate in file";
  }
  return reason;
}

export function importStatusLabel(
  status: ImportResultRow["status"],
  locale: Locale,
): string {
  if (status === "created") return locale === "zh-CN" ? "已创建" : "Created";
  if (status === "skipped") return locale === "zh-CN" ? "已跳过" : "Skipped";
  return locale === "zh-CN" ? "错误" : "Error";
}

export function importStatusVariant(
  status: ImportResultRow["status"],
): "default" | "secondary" | "destructive" {
  if (status === "created") return "default";
  if (status === "skipped") return "secondary";
  return "destructive";
}

export function batchTestStatusLabel(
  status: BatchModelTestStatus,
  locale: Locale,
) {
  if (status === "pending") return locale === "zh-CN" ? "等待中" : "Pending";
  if (status === "running") return locale === "zh-CN" ? "测试中" : "Running";
  if (status === "success") return locale === "zh-CN" ? "成功" : "Success";
  return locale === "zh-CN" ? "失败" : "Failed";
}

export function batchTestStatusVariant(
  status: BatchModelTestStatus,
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "success") return "default";
  if (status === "failed") return "destructive";
  if (status === "running") return "secondary";
  return "outline";
}

export function importResultRows(
  result: SiteBatchImportResult,
  locale: Locale,
): ImportResultRow[] {
  return [
    ...result.created.map((site, index) => ({
      key: `created-${site.id}`,
      index,
      name: site.name,
      status: "created" as const,
      reason: "",
    })),
    ...result.skipped.map((item) => ({
      key: `skipped-${item.index}-${item.name}`,
      index: item.index,
      name: item.name,
      status: "skipped" as const,
      reason: importReasonLabel(item.reason, locale),
    })),
    ...result.errors.map((item) => ({
      key: `error-${item.index}-${item.field}-${item.message}`,
      index: item.index,
      name: item.field,
      status: "error" as const,
      reason: item.message,
    })),
  ];
}

export const emptyForm = (locale: Locale = "zh-CN"): FormState => {
  const baseUrlId = createLocalId("baseurl");
  const credentialId = createLocalId("credential");
  return {
    name: "",
    base_urls: [
      {
        id: baseUrlId,
        url: "",
        name: "",
        enabled: true,
        supported_protocols: [],
      },
    ],
    credentials: [{ id: credentialId, name: "", api_key: "", enabled: true }],
    protocolConfigs: [
      emptyProtocolConfig(
        baseUrlId,
        defaultProtocolConfigName(0, locale),
        credentialId,
      ),
    ],
  };
};

export function fallbackCredentialName(index: number) {
  return `Key ${index + 1}`;
}

export function credentialIndexLabel(index: number, locale: string) {
  return locale === "zh-CN" ? `密钥 ${index + 1}` : `Key ${index + 1}`;
}

export function credentialLabel(
  item: { name: string },
  index: number,
  locale: string,
) {
  const name = item.name.trim();
  if (name) return name;
  return credentialIndexLabel(index, locale);
}

export function baseUrlIndexLabel(index: number, locale: string) {
  return locale === "zh-CN" ? `地址 ${index + 1}` : `URL ${index + 1}`;
}

export function baseUrlLabel(
  item: { name: string },
  index: number,
  locale: string,
) {
  const name = item.name.trim();
  if (name) return name;
  return baseUrlIndexLabel(index, locale);
}

export function defaultProtocolConfigName(index: number, locale: string) {
  return locale === "zh-CN" ? `组合 ${index + 1}` : `Combination ${index + 1}`;
}

export function protocolConfigDisplayName(
  item: { name?: string | null },
  index: number,
  locale: string,
) {
  const name = safeText(item.name).trim();
  return name || defaultProtocolConfigName(index, locale);
}

export function nextProtocolConfigName(
  protocolConfigs: Array<{ name?: string | null }>,
  locale: string,
) {
  const usedNames = new Set(
    protocolConfigs
      .map((item, index) =>
        protocolConfigDisplayName(item, index, locale).toLowerCase(),
      )
      .filter(Boolean),
  );
  for (
    let index = protocolConfigs.length;
    index < protocolConfigs.length + 1000;
    index += 1
  ) {
    const candidate = defaultProtocolConfigName(index, locale);
    if (!usedNames.has(candidate.toLowerCase())) {
      return candidate;
    }
  }
  return defaultProtocolConfigName(protocolConfigs.length, locale);
}

export function defaultBaseUrlId(
  items: Array<{ id: string; enabled: boolean }>,
) {
  return items.find((item) => item.enabled)?.id ?? items[0]?.id ?? "";
}

export function resolveBaseUrlId(
  items: Array<{ id: string; enabled: boolean }>,
  baseUrlId: string,
) {
  return items.some((item) => item.id === baseUrlId)
    ? baseUrlId
    : defaultBaseUrlId(items);
}

export function activeBaseUrlValue(
  form: FormState,
  protocolConfig: Pick<FormProtocolConfig, "base_url_id">,
) {
  const boundBaseUrl = protocolConfig.base_url_id
    ? form.base_urls.find((item) => item.id === protocolConfig.base_url_id)
    : undefined;
  if (boundBaseUrl) return boundBaseUrl.enabled ? boundBaseUrl.url : "";
  const enabledUrl = form.base_urls.find(
    (item) => item.enabled && item.url.trim(),
  )?.url;
  if (enabledUrl) return enabledUrl;
  return form.base_urls[0]?.url || "";
}

export function formHeaders(
  protocolConfig: Pick<FormProtocolConfig, "headers">,
) {
  return Object.fromEntries(
    protocolConfig.headers
      .map((entry) => [entry.key.trim(), entry.value] as const)
      .filter(([key]) => key),
  );
}

export function credentialDisplayName(
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

export function safeText(value: string | null | undefined) {
  return typeof value === "string" ? value : "";
}

export function formatCooldownDuration(seconds: number) {
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

export function modelBadgeClassName(enabled: boolean) {
  return enabled
    ? "inline-flex h-8 items-center gap-2 rounded-full border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-muted"
    : "inline-flex h-8 items-center gap-2 rounded-full border bg-muted/40 px-3 text-sm font-medium text-muted-foreground";
}

export function siteProtocols(site: Site) {
  return Array.from(
    new Set(
      site.protocols.flatMap((protocolConfig) => protocolConfig.protocols),
    ),
  );
}

export function siteSubtitle(site: Site, locale: "zh-CN" | "en-US") {
  return siteProtocols(site)
    .map((p) => protocolLabel(p, locale))
    .join(" / ");
}

export function siteEndpointSummary(site: Site, locale: string = "zh-CN") {
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

export function siteModelCount(site: Site) {
  return site.protocols.reduce(
    (total, protocolConfig) =>
      total + protocolConfig.models.filter((model) => model.enabled).length,
    0,
  );
}

export function isSiteEnabled(site: Site) {
  return site.protocols.some((protocolConfig) => protocolConfig.enabled);
}

export function getSiteFaviconCandidates(url: string) {
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

export function SiteFavicon({ url, name }: { url: string; name: string }) {
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

export function toForm(site: Site, locale: Locale = "zh-CN"): FormState {
  const baseUrls = site.base_urls.length
    ? site.base_urls.map((item) => ({
      id: item.id,
      url: item.url,
      name: item.name,
      enabled: item.enabled,
      supported_protocols: item.supported_protocols ?? [],
    }))
    : [
      {
        id: createLocalId("baseurl"),
        url: "",
        name: "",
        enabled: true,
        supported_protocols: [] as ProtocolKind[],
      },
    ];
  const credentials = site.credentials.map((item) => ({
    id: item.id,
    name: isGeneratedCredentialName(item.name) ? "" : item.name,
    api_key: item.api_key,
    enabled: item.enabled,
  }));
  return {
    name: site.name,
    base_urls: baseUrls,
    credentials,
    protocolConfigs: site.protocols.map(
      (protocolConfig, protocolConfigIndex) => {
        const modelGroups = new Map<string, FormModel>();
        for (const m of protocolConfig.models) {
          const key = `${m.credential_id}:${m.model_name}`;
          const existing = modelGroups.get(key);
          if (existing) {
            if (m.protocol && !existing.protocols.includes(m.protocol)) {
              existing.protocols.push(m.protocol);
            }
            if (m.id && m.protocol) {
              existing.protocolIds = {
                ...existing.protocolIds,
                [m.protocol]: m.id,
              };
            }
            existing.enabled = existing.enabled || m.enabled;
            if (!existing.id && m.id) existing.id = m.id;
          } else {
            modelGroups.set(key, {
              id: m.id ?? null,
              protocols: m.protocol ? [m.protocol] : [],
              protocolIds: m.id && m.protocol ? { [m.protocol]: m.id } : {},
              credential_id: m.credential_id,
              model_name: m.model_name,
              enabled: m.enabled,
            });
          }
        }
        return {
          id: protocolConfig.id,
          name: protocolConfigDisplayName(
            protocolConfig,
            protocolConfigIndex,
            locale,
          ),
          enabled: protocolConfig.enabled,
          headers: Object.entries(protocolConfig.headers).length
            ? Object.entries(protocolConfig.headers).map(([key, value]) => ({
              key,
              value,
            }))
            : [{ key: "", value: "" }],
          proxy_mode: protocolConfig.proxy_mode,
          channel_proxy: protocolConfig.channel_proxy,
          param_override: protocolConfig.param_override,
          match_regex: safeText(protocolConfig.match_regex),
          manual_model_name: "",
          manual_protocols: Array.from(
            new Set(protocolConfig.protocols ?? []),
          ),
          base_url_id: resolveBaseUrlId(baseUrls, protocolConfig.base_url_id),
          credential_id: protocolConfig.credential_id,
          auto_sync_enabled: protocolConfig.auto_sync_enabled,
          models: Array.from(modelGroups.values()),
          expanded: true,
        };
      },
    ),
  };
}

export function protocolConfigEffectiveProtocols(
  protocolConfig: Pick<FormProtocolConfig, "models">,
) {
  return Array.from(
    new Set(protocolConfig.models.flatMap((model) => model.protocols)),
  );
}

export function baseUrlProtocolMap(form: FormState) {
  const map = new Map<string, Set<ProtocolKind>>();
  for (const baseUrl of form.base_urls) {
    map.set(baseUrl.id, new Set());
  }
  for (const protocolConfig of form.protocolConfigs) {
    const protocols = protocolConfigEffectiveProtocols(protocolConfig);
    const set = map.get(protocolConfig.base_url_id);
    if (!set) continue;
    protocols.forEach((protocol) => set.add(protocol));
  }
  return map;
}

export function formBaseUrlsForPayload(form: FormState) {
  const protocolsByBaseUrl = baseUrlProtocolMap(form);
  return form.base_urls
    .map((item) => ({
      id: item.id,
      url: item.url.trim(),
      name: item.name.trim(),
      enabled: item.enabled,
      supported_protocols: Array.from(protocolsByBaseUrl.get(item.id) ?? []),
    }))
    .filter((item) => item.url);
}

export function toPayload(form: FormState): SitePayload {
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
    protocols: form.protocolConfigs.flatMap((protocolConfig) => {
      const credentialId = protocolConfig.credential_id;
      const protocolConfigProtocols =
        protocolConfigEffectiveProtocols(protocolConfig);
      const models = protocolConfig.models
        .flatMap((model) => {
          const effectiveProtocols = model.protocols.filter((p) =>
            protocolConfigProtocols.includes(p),
          );
          if (effectiveProtocols.length === 0) {
            return [];
          }
          return effectiveProtocols.map((proto) => ({
            id: model.protocolIds?.[proto] ?? null,
            protocol: proto,
            credential_id: model.credential_id,
            model_name: model.model_name.trim(),
            enabled: model.enabled,
          }));
        })
        .filter((model) => model.credential_id && model.model_name);
      if (!models.length) {
        return [];
      }
      return [
        {
          id: protocolConfig.id,
          name: protocolConfig.name.trim(),
          protocols: protocolConfigProtocols,
          enabled: protocolConfig.enabled,
          headers: Object.fromEntries(
            protocolConfig.headers
              .map((entry) => [entry.key.trim(), entry.value] as const)
              .filter(([key]) => key),
          ),
          proxy_mode: protocolConfig.proxy_mode,
          channel_proxy: protocolConfig.channel_proxy.trim(),
          param_override: protocolConfig.param_override.trim(),
          match_regex: safeText(protocolConfig.match_regex).trim(),
          base_url_id: protocolConfig.base_url_id,
          credential_id: credentialId,
          auto_sync_enabled: protocolConfig.auto_sync_enabled,
          models,
        },
      ];
    }),
  };
}

export function protocolConfigCredentialKeys(
  protocolConfig: FormProtocolConfig,
  baseUrlIds: Set<string>,
) {
  if (!baseUrlIds.has(protocolConfig.base_url_id)) return [];
  return protocolConfigEffectiveProtocols(protocolConfig).map((protocol) =>
    JSON.stringify([protocolConfig.base_url_id, protocol]),
  );
}

export function duplicateProtocolConfigKeys(
  protocolConfigs: FormProtocolConfig[],
  baseUrls: Array<{ id: string }>,
) {
  const baseUrlIds = new Set(baseUrls.map((item) => item.id));
  const counts = new Map<string, number>();
  for (const item of protocolConfigs) {
    if (protocolConfigEffectiveProtocols(item).length === 0) continue;
    for (const key of protocolConfigCredentialKeys(item, baseUrlIds)) {
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return new Set(
    [...counts.entries()].filter(([, count]) => count > 1).map(([key]) => key),
  );
}

export function invalidProtocolBaseUrlCount(form: FormState) {
  const baseUrlIds = new Set(
    formBaseUrlsForPayload(form).map((item) => item.id),
  );
  return form.protocolConfigs.filter(
    (item) =>
      protocolConfigEffectiveProtocols(item).length > 0 &&
      !baseUrlIds.has(item.base_url_id),
  ).length;
}

export function invalidModelProtocolCount(form: FormState) {
  return form.protocolConfigs.reduce((total, protocolConfig) => {
    return (
      total +
      protocolConfig.models.filter((model) => model.protocols.length === 0)
        .length
    );
  }, 0);
}
