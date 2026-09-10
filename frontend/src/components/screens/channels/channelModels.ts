import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  FormModel,
  FormProtocolConfig,
  FormSyncTarget,
  PickerModelItem,
} from "./channelTypes";

export function canRunModelAction(
  lastRunAt: Record<string, number>,
  key: string,
) {
  const now = Date.now();
  if (now - (lastRunAt[key] ?? 0) < 800) return false;
  lastRunAt[key] = now;
  return true;
}

export function activeSelectedCredentialIds(
  form: FormState,
  config: FormProtocolConfig,
) {
  const credentials = new Map(
    form.credentials.map((credential) => [credential.id, credential]),
  );
  return protocolConfigSelectedCredentialIds(config).filter((id) => {
    const credential = credentials.get(id);
    return Boolean(credential?.enabled && credential.api_key.trim());
  });
}

export function existingPickerModelKeys(config: FormProtocolConfig) {
  return new Set(
    [...config.models, ...config.sync_targets].map(genericModelKey),
  );
}

export function buildModels(
  config: FormProtocolConfig,
  credentialIds: string[],
  modelName: string,
  protocols: ProtocolKind[],
  source: "manual" | "synced",
) {
  const existing = new Set(
    config.models.map((model) => `${model.credential_id}:${model.model_name}`),
  );
  return credentialIds
    .filter((id) => !existing.has(`${id}:${modelName}`))
    .map((credential_id) => ({
      protocols,
      protocolIds: {},
      credential_id,
      model_name: modelName,
      enabled: true,
      source,
    }));
}

export function syncTargetKey(target: FormSyncTarget) {
  return JSON.stringify([
    target.credential_id,
    target.model_name,
    target.protocol,
  ]);
}

/** Builds a model key scoped by credential and model name. */
export function genericModelKey(
  model: Pick<PickerModelItem, "credential_id" | "model_name">,
) {
  return `${model.credential_id}:${model.model_name}`;
}

/** Builds a stable model key scoped to a protocol configuration. */
export function protocolConfigModelKey(
  protocolConfig: Pick<FormProtocolConfig, "id">,
  model: Pick<FormModel, "credential_id" | "model_name" | "source">,
) {
  return JSON.stringify([
    protocolConfig.id,
    model.credential_id,
    model.model_name,
    model.source,
  ]);
}

/** Builds the collapsed overview row key shared by same-name models. */
export function aggregateModelGroupKey(
  protocolConfig: Pick<FormProtocolConfig, "id">,
  modelName: string,
) {
  return JSON.stringify([protocolConfig.id, modelName]);
}

/** Reports whether a key targets a whole model group instead of one model. */
export function isAggregateModelGroupKey(key: string) {
  // Group keys hold two JSON parts; model keys hold four.
  return key.startsWith("[") && key.split(",").length === 2;
}

/** Merges form models that represent the same persisted model rows. */
export function coalesceFormModels(models: FormModel[]) {
  const groups = new Map<string, FormModel>();
  for (const model of models) {
    const key = JSON.stringify([
      model.credential_id,
      model.model_name,
      model.source,
    ]);
    const existing = groups.get(key);
    if (!existing) {
      groups.set(key, {
        ...model,
        protocols: Array.from(new Set(model.protocols)),
        protocolIds: { ...model.protocolIds },
      });
      continue;
    }
    existing.protocols = Array.from(
      new Set([...existing.protocols, ...model.protocols]),
    );
    existing.protocolIds = {
      ...existing.protocolIds,
      ...model.protocolIds,
    };
    existing.enabled = existing.enabled || model.enabled;
  }
  return Array.from(groups.values());
}

/** Deduplicates picker models by credential and model name. */
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

/** Groups picker rows by model name so one choice can cover every key. */
export function groupPickerModelsByName(models: PickerModelItem[]) {
  const groups = new Map<string, PickerModelItem[]>();
  for (const model of groupPickerModels(models)) {
    const items = groups.get(model.model_name);
    if (items) {
      items.push(model);
      continue;
    }
    groups.set(model.model_name, [model]);
  }
  return Array.from(groups, ([model_name, items]) => ({
    model_name,
    items,
  }));
}

/** Reports whether a picker model has an explicit protocol override. */
export function hasPickerModelProtocolOverride(
  overrides: Record<string, ProtocolKind[]>,
  key: string,
) {
  return Object.hasOwn(overrides, key);
}

/** Resolves picker protocols from an override or the shared fallback. */
export function resolvePickerModelProtocols(
  key: string,
  overrides: Record<string, ProtocolKind[]>,
  fallback: ProtocolKind[],
) {
  return hasPickerModelProtocolOverride(overrides, key)
    ? (overrides[key] ?? [])
    : fallback;
}

/** Returns the unique protocols supported by a form model. */
export function modelSupportedProtocols(
  model: Pick<FormModel, "protocols"> | null | undefined,
) {
  if (model?.protocols && model.protocols.length > 0) {
    return Array.from(new Set(model.protocols));
  }
  return [];
}

export function protocolConfigEffectiveProtocols(
  protocolConfig: Pick<
    FormProtocolConfig,
    "manual_protocols" | "models" | "sync_targets"
  >,
) {
  return Array.from(
    new Set([
      ...protocolConfig.manual_protocols,
      ...protocolConfig.models.flatMap((model) => model.protocols),
      ...protocolConfig.sync_targets.map((target) => target.protocol),
    ]),
  );
}

import type { Site, SiteProtocolConfig } from "@/lib/api/sites";

/** Builds a compact summary of a site's configured base URLs. */
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

/** Counts enabled model entries across a site's protocol configurations. */
export function siteModelCount(site: Site) {
  return site.protocols.reduce(
    (total, protocolConfig) =>
      total + protocolConfig.models.filter((model) => model.enabled).length,
    0,
  );
}

/** Reports whether a protocol configuration is enabled at every owning level. */
export function isSiteProtocolConfigEnabled(
  site: Site,
  protocolConfig: SiteProtocolConfig,
) {
  return site.enabled && protocolConfig.enabled;
}

/** Builds ordered favicon candidates for a valid site URL. */
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

import { formatCredentialDisplayName } from "@/lib/credentialLabels";
import { safeText } from "./channelForm";

/** Builds the fallback persisted name for a credential. */
export function fallbackCredentialName(index: number) {
  return `Key ${index + 1}`;
}

/** Formats a positional credential label for the requested locale. */
export function credentialIndexLabel(index: number, locale: string) {
  return locale === "zh-CN" ? `密钥 ${index + 1}` : `Key ${index + 1}`;
}

/** Returns a credential name or its localized positional fallback. */
export function credentialLabel(
  item: { name: string },
  index: number,
  locale: string,
) {
  return formatCredentialDisplayName(item.name, index + 1, locale);
}

/** Formats a positional base URL label for the requested locale. */
export function baseUrlIndexLabel(index: number, locale: string) {
  return locale === "zh-CN" ? `地址 ${index + 1}` : `URL ${index + 1}`;
}

/** Returns a base URL name or its localized positional fallback. */
export function baseUrlLabel(
  item: { name: string },
  index: number,
  locale: string,
) {
  const name = item.name.trim();
  if (name) return name;
  return baseUrlIndexLabel(index, locale);
}

/** Builds a localized default name for a protocol configuration. */
export function defaultProtocolConfigName(index: number, locale: string) {
  return locale === "zh-CN"
    ? `协议配置 ${index + 1}`
    : `Protocol config ${index + 1}`;
}

/** Returns a protocol configuration name or its localized fallback. */
export function protocolConfigDisplayName(
  item: { name?: string | null },
  index: number,
  locale: string,
) {
  const name = safeText(item.name).trim();
  return name || defaultProtocolConfigName(index, locale);
}

/** Finds the next unused localized protocol configuration name. */
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

import type { Locale } from "@/lib/I18nContext";
import type { FormCredential, FormState } from "./channelTypes";

/** Creates a client-side identifier for unsaved channel entities. */
export function createLocalId(prefix: string) {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function emptyCredential(): FormCredential {
  return {
    id: createLocalId("credential"),
    name: "",
    api_key: "",
    enabled: true,
    rate_source: "none",
    rate_protocol_config_id: "",
    rate_group: "",
    rate_multiplier: null,
    rate_observed_at: null,
    rate_last_synced_at: null,
    rate_last_error: "",
  };
}

/** Creates a new protocol configuration with editor defaults. */
export const emptyProtocolConfig = (
  baseUrlId = "",
  name = "",
  credentialId = "",
): FormProtocolConfig => ({
  id: createLocalId("protocol"),
  name,
  enabled: true,
  headers: [{ key: "", value: "", action: "override" }],
  proxy_mode: "inherit",
  channel_proxy: "",
  param_override: [],
  model_filter: "",
  sync_new_models: false,
  manual_model_name: "",
  manual_protocols: [],
  base_url_id: baseUrlId,
  credential_ids: credentialId ? [credentialId] : [],
  sync_targets: [],
  models: [],
  expanded: true,
});

/** Creates a channel editor form with one URL, credential, and protocol config. */
export const emptyForm = (locale: Locale = "zh-CN"): FormState => {
  const baseUrlId = createLocalId("baseurl");
  const credential = emptyCredential();
  return {
    name: "",
    tags: [],
    base_urls: [
      {
        id: baseUrlId,
        url: "",
        name: "",
        enabled: true,
        supported_protocols: [],
      },
    ],
    credentials: [credential],
    protocolConfigs: [
      emptyProtocolConfig(
        baseUrlId,
        defaultProtocolConfigName(0, locale),
        credential.id,
      ),
    ],
  };
};

import { protocolConfigSelectedCredentialIds } from "./channelForm";
import { formBaseUrlsForPayload } from "./channelFormConversion";

/** Builds uniqueness keys for a protocol configuration's credentials. */
export function protocolConfigCredentialKeys(
  protocolConfig: FormProtocolConfig,
  baseUrlIds: Set<string>,
) {
  if (!baseUrlIds.has(protocolConfig.base_url_id)) return [];
  const credentialIds = protocolConfigSelectedCredentialIds(protocolConfig);
  return credentialIds.flatMap((credentialId) =>
    protocolConfigEffectiveProtocols(protocolConfig).map((protocol) =>
      JSON.stringify([protocolConfig.base_url_id, credentialId, protocol]),
    ),
  );
}

/** Finds duplicated base URL, credential, and protocol combinations. */
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

/** Counts protocol configurations bound to unavailable base URLs. */
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

/** Counts form models that have no selected protocol. */
export function invalidModelProtocolCount(form: FormState) {
  return form.protocolConfigs.reduce((total, protocolConfig) => {
    return (
      total +
      protocolConfig.models.filter((model) => model.protocols.length === 0)
        .length
    );
  }, 0);
}
