import type { ProtocolKind } from "@/lib/api/protocols";
import type { Site } from "@/lib/api/sites";
import { formatCredentialDisplayName } from "@/lib/credentialLabels";
import { PROTOCOL_LIST } from "@/lib/protocols";
import { protocolConfigSelectedCredentialIds } from "./channelForm";
import { formBaseUrlsForPayload } from "./channelFormConversion";
import type {
  FormCredential,
  FormModel,
  FormProtocolConfig,
  FormState,
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
    return Boolean(credential?.api_key.trim());
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

/** Returns the unique protocols supported by a form model. */
export function modelSupportedProtocols(
  model: Pick<FormModel, "protocols"> | null | undefined,
): ProtocolKind[] {
  if (model?.protocols && model.protocols.length > 0) {
    if (model.protocols.includes("auto")) return PROTOCOL_LIST;
    return Array.from(new Set(model.protocols));
  }
  return [];
}

export function protocolConfigEffectiveProtocols(
  protocolConfig: Pick<FormProtocolConfig, "models" | "sync_targets">,
): ProtocolKind[] {
  return Array.from(
    new Set([
      ...protocolConfig.models.flatMap((model) => model.protocols),
      ...protocolConfig.sync_targets.map((target) => target.protocol),
    ]),
  );
}

/** Lists configured base URLs. */
export function siteEndpointUrls(site: Site) {
  return site.base_urls.map((item) => item.url.trim()).filter(Boolean);
}

/** Builds a compact summary of a site's configured base URLs. */
export function siteEndpointSummary(site: Site, locale: string = "zh-CN") {
  const urls = siteEndpointUrls(site);
  if (urls.length <= 1) return urls[0] ?? "";
  const extraCount = urls.length - 1;
  const suffix =
    locale === "zh-CN" ? ` + ${extraCount}个地址` : ` + ${extraCount} more`;
  return urls[0] + suffix;
}

/** Counts enabled and total model entries for a site. */
export function siteModelCounts(site: Site) {
  let enabled = 0;
  let total = 0;
  for (const protocolConfig of site.protocols) {
    for (const model of protocolConfig.models) {
      total += 1;
      if (model.enabled) enabled += 1;
    }
  }
  return { enabled, total };
}

/** Lists enabled protocol kinds on a site, in canonical order. */
export function siteEnabledProtocols(site: Site): ProtocolKind[] {
  const kinds = new Set<ProtocolKind>();
  for (const protocolConfig of site.protocols) {
    for (const protocol of protocolConfig.protocols) {
      kinds.add(protocol);
    }
  }
  return (["auto", ...PROTOCOL_LIST] as ProtocolKind[]).filter((protocol) =>
    kinds.has(protocol),
  );
}

/** Builds the fallback persisted name for a credential. */
export function fallbackCredentialName(index: number) {
  return `Key ${index + 1}`;
}

/** Returns a credential name or its localized positional fallback. */
export function credentialLabel(
  item: { name: string },
  index: number,
  locale: string,
) {
  return formatCredentialDisplayName(item.name, index + 1, locale);
}

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

export function emptyCredential(baseUrlId = ""): FormCredential {
  return {
    id: createLocalId("credential"),
    name: "",
    api_key: "",
    rate_source: "none",
    rate_protocol_config_id: "",
    rate_group: "",
    rate_multiplier: null,
    rate_observed_at: null,
    rate_last_synced_at: null,
    rate_last_error: "",
    baseUrlId,
  };
}

/** Splits a bulk key textarea into unique API keys. */
export function parseApiKeyLines(value: string) {
  const keys: string[] = [];
  for (const line of value.split(/\r?\n/)) {
    const apiKey = line.trim();
    if (apiKey && !keys.includes(apiKey)) keys.push(apiKey);
  }
  return keys;
}

/** Masks a stored API key for the existing-key list. */
export function maskApiKey(value: string) {
  const key = value.trim();
  if (key.length <= 8) return "••••";
  return `${key.slice(0, Math.min(4, key.length - 4))}****${key.slice(-4)}`;
}

export function isPendingCredentialId(id: string) {
  return id.startsWith("pending-");
}

/** Replaces pending keys for one URL while keeping persisted keys. */
export function replacePendingCredentials(
  credentials: FormCredential[],
  lines: string,
  baseUrlId: string,
) {
  const kept = credentials.filter(
    (item) => item.baseUrlId !== baseUrlId || !isPendingCredentialId(item.id),
  );
  const previousPending = new Map(
    credentials
      .filter(
        (item) =>
          item.baseUrlId === baseUrlId && isPendingCredentialId(item.id),
      )
      .map((item) => [item.api_key, item]),
  );
  const pending = parseApiKeyLines(lines).map((apiKey) => {
    const existing = previousPending.get(apiKey);
    if (existing) return existing;
    return {
      ...emptyCredential(baseUrlId),
      id: `pending-${createLocalId("credential")}`,
      api_key: apiKey,
    };
  });
  return [...kept, ...pending];
}

/** Creates a new protocol configuration with editor defaults. */
export const emptyProtocolConfig = (
  baseUrlId = "",
  credentialIds: string[] = [],
): FormProtocolConfig => ({
  id: createLocalId("protocol"),
  base_url_id: baseUrlId,
  credential_ids: [...credentialIds],
  sync_targets: [],
  models: [],
});

/** Creates a channel editor form with one URL and protocol config. */
export const emptyForm = (): FormState => {
  const baseUrlId = createLocalId("baseurl");
  return {
    name: "",
    tags: [],
    newApiKeysLines: "",
    base_urls: [
      {
        id: baseUrlId,
        url: "",
        shareKeys: true,
        newApiKeysLines: "",
      },
    ],
    credentials: [],
    protocolConfigs: [emptyProtocolConfig(baseUrlId)],
    proxy_mode: "inherit",
    channel_proxy: "",
    headersJson: "",
    paramsJson: "",
  };
};

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
