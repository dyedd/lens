import type { ProtocolKind } from "@/lib/api/protocols";
import type { Site } from "@/lib/api/sites";
import { formatCredentialDisplayName } from "@/lib/credentialLabels";
import { protocolConfigSelectedCredentialIds } from "./channelForm";
import { formBaseUrlsForPayload } from "./channelFormConversion";
import type {
  FormCredential,
  FormModel,
  FormProtocolConfig,
  FormState,
} from "./channelTypes";

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

/** Builds a stable model key scoped to a protocol configuration. */
export function protocolConfigModelKey(
  protocolConfig: Pick<FormProtocolConfig, "id">,
  model: Pick<FormModel, "credential_id" | "model_name">,
) {
  return JSON.stringify([
    protocolConfig.id,
    model.credential_id,
    model.model_name,
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
  try {
    const parts: unknown = JSON.parse(key);
    return (
      Array.isArray(parts) &&
      parts.length === 2 &&
      parts.every((part) => typeof part === "string")
    );
  } catch {
    return false;
  }
}

/** Merges form models that represent the same persisted model rows. */
export function coalesceFormModels(models: FormModel[]) {
  const groups = new Map<string, FormModel>();
  for (const model of models) {
    const key = JSON.stringify([model.credential_id, model.model_name]);
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
    existing.context_window ??= model.context_window;
    existing.upstream_context_window ??= model.upstream_context_window;
    existing.catalog_context_window ??= model.catalog_context_window ?? null;
  }
  return Array.from(groups.values());
}

/** Returns the unique protocols supported by a form model. */
export function modelSupportedProtocols(
  model: Pick<FormModel, "protocols"> | null | undefined,
): ProtocolKind[] {
  if (model?.protocols && model.protocols.length > 0) {
    return Array.from(new Set(model.protocols));
  }
  return [];
}

export function protocolConfigEffectiveProtocols(
  protocolConfig: Pick<FormProtocolConfig, "models">,
): ProtocolKind[] {
  return Array.from(
    new Set(protocolConfig.models.flatMap((model) => model.protocols)),
  );
}

/** Lists configured base URLs. */
export function siteEndpointUrls(site: Site) {
  return site.base_urls.map((item) => item.url.trim()).filter(Boolean);
}

/** Shortens a base URL for dense table cells. */
export function formatBaseUrlLabel(url: string) {
  return url.replace(/^https?:\/\//, "").replace(/\/+$/, "");
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

/** Counts enabled and total model entries for one site. */
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

/** Builds the whole-name filter that selects exactly this model. */
export function escapeModelName(modelName: string) {
  return `^${modelName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`;
}

/** Appends exact-name filters to a key's pattern, skipping ones it has. */
export function mergeModelPatterns(
  current: string,
  additions: string[],
): string {
  // 后端始终忽略大小写；把标记包进分支会让 Python 拒绝合并后的表达式。
  const existing = current
    .trim()
    .replace(/^\(\?[aiLmsux]+\)/, "")
    .trim();
  if (existing === "*") return existing;
  const fresh = additions
    .map((addition) => addition.trim())
    .filter((addition) => addition && !existing.includes(addition));
  if (!fresh.length) return existing;
  // 当前规则包成一个分支，避免已有的 `|` 吞掉追加的模型名。
  return [existing ? `(?:${existing})` : "", ...fresh]
    .filter(Boolean)
    .join("|");
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

/** Formats a key as its label plus masked value for selectors and tooltips. */
export function formatCredentialTitle(
  item: { name: string; api_key: string },
  index: number,
  locale: string,
) {
  return `${credentialLabel(item, index, locale)} · ${maskApiKey(item.api_key)}`;
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

function emptyCredential(baseUrlId = ""): FormCredential {
  return {
    id: createLocalId("credential"),
    name: "",
    api_key: "",
    model_pattern: "",
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

/** Splits a bulk key draft into unique API keys. */
function parseApiKeyLines(value: string) {
  const keys: string[] = [];
  for (const line of value.split(/\r?\n/)) {
    const apiKey = line.trim();
    if (apiKey && !keys.includes(apiKey)) keys.push(apiKey);
  }
  return keys;
}

function apiKeyDraft(form: FormState, baseUrlId: string) {
  if (!baseUrlId) return form.newApiKeysLines;
  return (
    form.base_urls.find((item) => item.id === baseUrlId)?.newApiKeysLines ?? ""
  );
}

function clearApiKeyDraft(form: FormState, baseUrlId: string): FormState {
  if (!baseUrlId) return { ...form, newApiKeysLines: "" };
  return {
    ...form,
    base_urls: form.base_urls.map((item) =>
      item.id === baseUrlId ? { ...item, newApiKeysLines: "" } : item,
    ),
  };
}

/** Appends new keys for one URL. Keys already on that URL stay as they are. */
function appendApiKeyLines(
  credentials: FormCredential[],
  lines: string,
  baseUrlId: string,
) {
  const existing = new Set(
    credentials
      .filter((item) => item.baseUrlId === baseUrlId)
      .map((item) => item.api_key.trim()),
  );
  const added: FormCredential[] = [];
  for (const apiKey of parseApiKeyLines(lines)) {
    if (existing.has(apiKey)) continue;
    existing.add(apiKey);
    added.push({
      ...emptyCredential(baseUrlId),
      id: `pending-${createLocalId("credential")}`,
      api_key: apiKey,
    });
  }
  return added.length ? [...credentials, ...added] : credentials;
}

/** Moves one URL's draft into the key list so each key can take a remark. */
export function addApiKeyDraft(
  form: FormState,
  baseUrlId: string,
): { form: FormState; added: number } {
  const lines = apiKeyDraft(form, baseUrlId);
  const keys = parseApiKeyLines(lines);
  if (!keys.length) return { form, added: 0 };
  const credentials = appendApiKeyLines(form.credentials, lines, baseUrlId);
  return {
    form: { ...clearApiKeyDraft(form, baseUrlId), credentials },
    added: credentials.length - form.credentials.length,
  };
}

/** Moves every visible key draft into the list. */
export function acceptApiKeyDrafts(form: FormState): FormState {
  const separateUrls = form.base_urls.filter((url) => url.shareKeys === false);
  let next = addApiKeyDraft(form, "").form;
  for (const url of separateUrls) next = addApiKeyDraft(next, url.id).form;
  return next;
}

/** Includes draft lines that have not been moved into the key list yet. */
export function applyApiKeyDrafts(form: FormState): FormState {
  const accepted = acceptApiKeyDrafts(form);
  if (accepted.credentials === form.credentials) return form;
  return { ...form, credentials: accepted.credentials };
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

/** Drops the editor-only pending marker so saved keys keep a plain ID. */
export function persistedCredentialId(id: string) {
  return isPendingCredentialId(id) ? id.slice("pending-".length) : id;
}

/** Creates a new protocol configuration with editor defaults. */
export const emptyProtocolConfig = (
  baseUrlId = "",
  credentialIds: string[] = [],
): FormProtocolConfig => ({
  id: createLocalId("protocol"),
  base_url_id: baseUrlId,
  credential_ids: [...credentialIds],
  protocols: [],
  models: [],
});

/** Creates a channel editor form with one Chat Completions endpoint. */
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
        kind: "default",
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
