import type { HeaderRule } from "@/lib/upstreamRules";
import { headerDraftToRules } from "@/lib/upstreamRules";
import { headerDraftsFromJson } from "./channelAdvancedJson";
import { protocolConfigEffectiveProtocols } from "./channelModels";
import type {
  FormCredential,
  FormProtocolConfig,
  FormState,
} from "./channelTypes";

/** Selects the first base URL. */
function defaultBaseUrlId(items: Array<{ id: string }>) {
  return items[0]?.id ?? "";
}

/** Keeps a valid base URL selection or chooses the default selection. */
export function resolveBaseUrlId(
  items: Array<{ id: string }>,
  baseUrlId: string,
) {
  return items.some((item) => item.id === baseUrlId)
    ? baseUrlId
    : defaultBaseUrlId(items);
}

/** Resolves the active base URL value for a protocol configuration. */
export function activeBaseUrlValue(
  form: Pick<FormState, "base_urls">,
  protocolConfig: Pick<FormProtocolConfig, "base_url_id">,
) {
  const boundBaseUrl = protocolConfig.base_url_id
    ? form.base_urls.find((item) => item.id === protocolConfig.base_url_id)
    : undefined;
  if (boundBaseUrl?.url.trim()) return boundBaseUrl.url;
  return (
    form.base_urls.find((item) => item.url.trim())?.url ||
    form.base_urls[0]?.url ||
    ""
  );
}

/** Converts the editor header JSON into upstream header rules. */
export function formHeaders(
  form: Pick<FormState, "headersJson">,
): HeaderRule[] {
  return headerDraftToRules(headerDraftsFromJson(form.headersJson) ?? []);
}

export function canonicalizeCredentialIds(values: string[]) {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)));
}

/** Returns the unique selected credential IDs for a protocol configuration. */
export function protocolConfigSelectedCredentialIds(
  protocolConfig: Pick<FormProtocolConfig, "credential_ids">,
) {
  return canonicalizeCredentialIds(protocolConfig.credential_ids);
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

function isPendingCredentialId(id: string) {
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
    form.base_urls.filter((item) => item.url.trim()).map((item) => item.id),
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
