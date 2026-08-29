import { formBaseUrlsForPayload } from "./channelFormConversion";
import { protocolConfigSelectedCredentialIds } from "./channelFormUtils";
import { protocolConfigEffectiveProtocols } from "./channelModelUtils";
import type { FormProtocolConfig, FormState } from "./channelTypes";

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
