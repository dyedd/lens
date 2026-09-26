import type { ProtocolKind } from "@/lib/api/protocols";
import type { Site, SitePayload } from "@/lib/api/sites";
import { isGeneratedCredentialName } from "@/lib/credentialLabels";
import {
  headerDraftToRules,
  headerRulesToDraft,
  paramOverrideDraftToRules,
  paramOverrideRulesToDraft,
} from "@/lib/upstreamRules";

import {
  headerDraftsFromJson,
  headerDraftsToJson,
  paramDraftsFromJson,
  paramDraftsToJson,
} from "./channelAdvancedJson";
import { canonicalizeCredentialIds, resolveBaseUrlId } from "./channelForm";
import {
  coalesceFormModels,
  createLocalId,
  emptyProtocolConfig,
  fallbackCredentialName,
  persistedCredentialId,
  protocolConfigEffectiveProtocols,
} from "./channelModels";
import type {
  FormCredential,
  FormModel,
  FormProtocolConfig,
  FormState,
} from "./channelTypes";

function credentialIdsForUrl(
  form: Pick<FormState, "base_urls" | "credentials">,
  urlId: string,
) {
  const primaryId = form.base_urls[0]?.id ?? "";
  const isPrimary = urlId === primaryId;
  const url = form.base_urls.find((item) => item.id === urlId);
  if (isPrimary || url?.shareKeys !== false) {
    return form.credentials
      .filter((item) => item.api_key.trim() && !item.baseUrlId)
      .map((item) => item.id);
  }
  return form.credentials
    .filter((item) => item.api_key.trim() && item.baseUrlId === urlId)
    .map((item) => item.id);
}

function remapModelsToCredentials(
  models: FormModel[],
  credentialIds: string[],
): FormModel[] {
  if (!models.length || !credentialIds.length) return [];
  const templates = new Map<string, FormModel>();
  for (const model of models) {
    const key = JSON.stringify([
      model.model_name,
      model.source,
      [...model.protocols].sort(),
    ]);
    if (!templates.has(key)) templates.set(key, model);
  }
  return Array.from(templates.values()).flatMap((template) =>
    credentialIds.map((credentialId) => ({
      ...template,
      credential_id: credentialId,
      protocolIds:
        template.credential_id === credentialId ? template.protocolIds : {},
    })),
  );
}

/** Rebuilds one protocol config per base URL with the keys it can use. */
export function rebuildProtocolConfigs(form: FormState): FormProtocolConfig[] {
  const urls = form.base_urls.filter((item) => item.url.trim());
  const existingByUrl = new Map(
    form.protocolConfigs.map((config) => [config.base_url_id, config] as const),
  );
  const primaryConfig = form.protocolConfigs[0];
  return urls.map((url) => {
    const credentialIds = credentialIdsForUrl(form, url.id);
    const existing = existingByUrl.get(url.id);
    const source = existing ?? primaryConfig;
    const protocols = protocolConfigEffectiveProtocols({
      models: existing?.models ?? source?.models ?? [],
    });
    const models = existing?.models.length
      ? existing.models.filter((model) =>
          credentialIds.includes(model.credential_id),
        )
      : remapModelsToCredentials(source?.models ?? [], credentialIds);
    const base =
      existing ??
      ({
        ...emptyProtocolConfig(url.id, credentialIds),
        id: `proto-${url.id}`,
      } satisfies FormProtocolConfig);
    return {
      ...base,
      base_url_id: url.id,
      credential_ids: credentialIds,
      protocols: protocols.length
        ? protocols
        : (existing?.protocols ?? source?.protocols ?? []),
      models: coalesceFormModels(models),
    };
  });
}

/** Converts a persisted site into channel editor state. */
export function toForm(site: Site): FormState {
  const baseUrls = site.base_urls.length
    ? site.base_urls.map((item) => ({
        id: item.id,
        url: item.url,
        shareKeys: true,
        newApiKeysLines: "",
      }))
    : [
        {
          id: createLocalId("baseurl"),
          url: "",
          shareKeys: true,
          newApiKeysLines: "",
        },
      ];
  const primaryId = baseUrls[0]?.id ?? "";
  for (const url of baseUrls.slice(1)) {
    url.shareKeys = !site.credentials.some(
      (item) => item.base_url_id === url.id,
    );
  }
  const credentials: FormCredential[] = site.credentials.map((item) => ({
    id: persistedCredentialId(item.id),
    name: isGeneratedCredentialName(item.name) ? "" : item.name,
    api_key: item.api_key,
    rate_source: item.rate_source,
    rate_protocol_config_id: item.rate_protocol_config_id,
    rate_group: item.rate_group,
    rate_multiplier: item.rate_multiplier,
    rate_observed_at: item.rate_observed_at,
    rate_last_synced_at: item.rate_last_synced_at,
    rate_last_error: item.rate_last_error,
    baseUrlId:
      item.base_url_id && item.base_url_id !== primaryId
        ? item.base_url_id
        : "",
  }));
  const protocolConfigs = site.protocols.map((protocolConfig) => {
    const models = coalesceFormModels(
      protocolConfig.models.map((model) => ({
        protocols: model.protocol ? [model.protocol] : [],
        protocolIds: model.protocol ? { [model.protocol]: model.id } : {},
        credential_id: persistedCredentialId(model.credential_id),
        model_name: model.model_name,
        enabled: model.enabled,
        source: model.source,
        upstream_missing: model.upstream_missing,
      })),
    );
    const credentialIds = canonicalizeCredentialIds(
      protocolConfig.credential_ids.map(persistedCredentialId),
    );
    return {
      id: protocolConfig.id,
      base_url_id: resolveBaseUrlId(baseUrls, protocolConfig.base_url_id),
      credential_ids: credentialIds,
      protocols: protocolConfig.protocols,
      models,
    };
  });
  const draft: FormState = {
    name: site.name,
    tags: site.tags,
    newApiKeysLines: "",
    base_urls: baseUrls,
    credentials,
    protocolConfigs,
    proxy_mode: site.proxy_mode,
    channel_proxy: site.channel_proxy,
    headersJson: headerDraftsToJson(headerRulesToDraft(site.headers)),
    paramsJson: paramDraftsToJson(
      paramOverrideRulesToDraft(site.param_override),
    ),
    model_sync_enabled: site.model_sync_enabled,
    model_sync_include: site.model_sync_include,
    model_sync_exclude: site.model_sync_exclude,
  };
  return {
    ...draft,
    protocolConfigs: rebuildProtocolConfigs(draft),
  };
}

/** Keeps a key's rate config when it still serves the key, else the first that does. */
function resolveRateProtocolConfigId(
  credential: FormCredential,
  protocolConfigs: FormProtocolConfig[],
) {
  if (credential.rate_source === "none") return "";
  const configIds = protocolConfigs
    .filter((config) => config.credential_ids.includes(credential.id))
    .map((config) => config.id);
  return configIds.includes(credential.rate_protocol_config_id)
    ? credential.rate_protocol_config_id
    : (configIds[0] ?? "");
}

/** Prepare base URLs for the site payload. */
export function formBaseUrlsForPayload(form: FormState) {
  return form.base_urls
    .map((item) => ({
      id: item.id,
      url: item.url.trim(),
    }))
    .filter((item) => item.url);
}

/** Converts channel editor state into a site payload. */
export function toPayload(form: FormState): SitePayload {
  const rebuilt = {
    ...form,
    protocolConfigs: rebuildProtocolConfigs(form),
  };
  const baseUrls = formBaseUrlsForPayload(rebuilt);
  const credentials = rebuilt.credentials.filter((item) => item.api_key.trim());
  return {
    name: rebuilt.name.trim(),
    tags: rebuilt.tags,
    proxy_mode: rebuilt.proxy_mode,
    channel_proxy: rebuilt.channel_proxy.trim(),
    headers: headerDraftToRules(
      headerDraftsFromJson(rebuilt.headersJson) ?? [],
    ),
    param_override: paramOverrideDraftToRules(
      paramDraftsFromJson(rebuilt.paramsJson) ?? [],
    ),
    model_sync_enabled: rebuilt.model_sync_enabled,
    model_sync_include: rebuilt.model_sync_include.trim(),
    model_sync_exclude: rebuilt.model_sync_exclude.trim(),
    base_urls: baseUrls,
    credentials: credentials.map((item, index) => ({
      id: persistedCredentialId(item.id),
      name: item.name.trim() || fallbackCredentialName(index),
      api_key: item.api_key.trim(),
      base_url_id: item.baseUrlId,
      rate_source: item.rate_source,
      rate_protocol_config_id: resolveRateProtocolConfigId(
        item,
        rebuilt.protocolConfigs,
      ),
      rate_group: item.rate_group.trim(),
    })),
    protocols: rebuilt.protocolConfigs.flatMap((protocolConfig) => {
      const selectedCredentialIds = protocolConfig.credential_ids.filter((id) =>
        credentials.some((item) => item.id === id),
      );
      if (!selectedCredentialIds.length) return [];
      const derivedProtocols = protocolConfigEffectiveProtocols(protocolConfig);
      const configuredProtocols = derivedProtocols.length
        ? derivedProtocols
        : protocolConfig.protocols;
      const protocolConfigProtocols = configuredProtocols.length
        ? configuredProtocols
        : (["auto"] as ProtocolKind[]);
      const models = protocolConfig.models
        .flatMap((model) => {
          const effectiveProtocols = model.protocols.filter((protocol) =>
            protocolConfigProtocols.includes(protocol),
          );
          if (effectiveProtocols.length === 0) {
            return [];
          }
          return effectiveProtocols.map((protocol) => ({
            id: model.protocolIds[protocol] ?? null,
            protocol,
            credential_id: persistedCredentialId(model.credential_id),
            model_name: model.model_name.trim(),
            enabled: model.enabled,
            source: model.source,
            upstream_missing: model.upstream_missing,
          }));
        })
        .filter((model) => model.credential_id && model.model_name);
      return [
        {
          id: protocolConfig.id,
          base_url_id: protocolConfig.base_url_id,
          protocols: protocolConfigProtocols,
          models,
        },
      ];
    }),
  };
}
