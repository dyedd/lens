import type {
  FormProtocolConfig,
  FormState,
  ModelQueryInputKind,
} from "./channelTypes";

/** Selects the first enabled base URL, falling back to the first item. */
export function defaultBaseUrlId(
  items: Array<{ id: string; enabled: boolean }>,
) {
  return items.find((item) => item.enabled)?.id ?? items[0]?.id ?? "";
}

/** Keeps a valid base URL selection or chooses the default selection. */
export function resolveBaseUrlId(
  items: Array<{ id: string; enabled: boolean }>,
  baseUrlId: string,
) {
  return items.some((item) => item.id === baseUrlId)
    ? baseUrlId
    : defaultBaseUrlId(items);
}

/** Resolves the active base URL value for a protocol configuration. */
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

/** Converts editable header rows into a request header record. */
export function formHeaders(
  protocolConfig: Pick<FormProtocolConfig, "headers">,
) {
  return Object.fromEntries(
    protocolConfig.headers
      .map((entry) => [entry.key.trim(), entry.value] as const)
      .filter(([key]) => key),
  );
}

/** Normalizes nullable text to a string. */
export function safeText(value: string | null | undefined) {
  return typeof value === "string" ? value : "";
}

export function normalizeCredentialIds(values: string[]) {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)));
}

/** Returns the unique selected credential IDs for a protocol configuration. */
export function protocolConfigSelectedCredentialIds(
  protocolConfig: Pick<FormProtocolConfig, "credential_id" | "credential_ids">,
) {
  const credentialIds = protocolConfig.credential_ids.length
    ? protocolConfig.credential_ids
    : [protocolConfig.credential_id];
  return normalizeCredentialIds(credentialIds);
}

/** Classifies model query input as empty, plain text, or a regular expression. */
export function classifyModelQueryInput(value: string): ModelQueryInputKind {
  const query = safeText(value).trim();
  if (!query) return "empty";
  if (query.startsWith("(?")) return "regex";
  if (query.includes(".*") || query.includes(".+") || query.includes(".?")) {
    return "regex";
  }
  if (/[\\^$()[\]{}|+*?]/.test(query)) return "regex";
  return "plain";
}

/** Reports whether a model query is a valid regular expression. */
export function isValidModelQueryRegex(value: string) {
  try {
    new RegExp(value);
    return true;
  } catch {
    return false;
  }
}

export function protocolConfigAutoSyncActive(
  protocolConfig: Pick<FormProtocolConfig, "auto_sync_enabled" | "match_regex">,
) {
  return (
    protocolConfig.auto_sync_enabled &&
    classifyModelQueryInput(protocolConfig.match_regex) === "regex"
  );
}
