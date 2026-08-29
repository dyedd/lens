import type { HeaderRule } from "@/lib/api/groups";
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

/** Converts editable header rows into upstream header rules. */
export function formHeaders(
  protocolConfig: Pick<FormProtocolConfig, "headers">,
): HeaderRule[] {
  return protocolConfig.headers
    .filter((entry) => entry.key.trim())
    .map((entry) => ({
      name: entry.key.trim(),
      value: entry.value,
      action: entry.action,
    }));
}

/** Coerce nullable text to a string. */
export function safeText(value: string | null | undefined) {
  return typeof value === "string" ? value : "";
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
