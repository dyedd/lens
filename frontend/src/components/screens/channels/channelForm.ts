import type { HeaderRule } from "@/lib/api/groups";
import { headerDraftToRules } from "@/lib/upstreamRules";
import { headerDraftsFromJson } from "./channelAdvancedJson";
import type { FormProtocolConfig, FormState } from "./channelTypes";

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
