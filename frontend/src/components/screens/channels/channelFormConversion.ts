import type { ProtocolKind } from "@/lib/api/protocols";
import type { Site, SitePayload } from "@/lib/api/sites";
import {
  fallbackCredentialName,
  isGeneratedCredentialName,
} from "@/lib/credentialLabels";
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
import {
  applyApiKeyDrafts,
  canonicalizeCredentialIds,
  createLocalId,
  emptyProtocolConfig,
  persistedCredentialId,
} from "./channelForm";
import {
  coalesceFormModels,
  protocolConfigEffectiveProtocols,
} from "./channelModels";
import type {
  FormBaseUrl,
  FormCredential,
  FormProtocolConfig,
  FormState,
} from "./channelTypes";

const endpointProtocolByKind: Partial<
  Record<FormBaseUrl["kind"], ProtocolKind>
> = {
  openai_chat: "openai_chat",
  openai_responses: "openai_responses",
  openai_embedding: "openai_embedding",
  openai_image: "openai_image",
  anthropic: "anthropic",
  gemini: "gemini",
  rerank: "rerank",
};

export function protocolForEndpointKind(
  kind: FormBaseUrl["kind"] | undefined,
): ProtocolKind {
  return (kind && endpointProtocolByKind[kind]) ?? "openai_chat";
}

export function credentialIdsForUrl(
  form: Pick<FormState, "credentials">,
  urlId: string,
) {
  return form.credentials
    .filter(
      (item) =>
        item.api_key.trim() &&
        (item.base_url_ids === null || item.base_url_ids.includes(urlId)),
    )
    .map((item) => item.id);
}

/** Rebuilds one protocol config per base URL with the keys it can use. */
export function rebuildProtocolConfigs(form: FormState): FormProtocolConfig[] {
  const urls = form.base_urls.filter(
    (item) => item.url.trim() && item.kind !== "models",
  );
  const existingByUrl = new Map(
    form.protocolConfigs.map((config) => [config.base_url_id, config] as const),
  );
  return urls.map((url) => {
    const credentialIds = credentialIdsForUrl(form, url.id);
    const existing = existingByUrl.get(url.id);
    const models = (existing?.models ?? []).filter((model) =>
      credentialIds.includes(model.credential_id),
    );
    const protocols = protocolConfigEffectiveProtocols({ models });
    const fallbackProtocols = (existing?.protocols ?? []).filter((protocol) =>
      endpointSupportsProtocol(url.kind, [protocol]),
    );
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
        : fallbackProtocols.length
          ? fallbackProtocols
          : [protocolForEndpointKind(url.kind)],
      models: coalesceFormModels(models),
    };
  });
}

export function endpointSupportsProtocol(
  kind: FormBaseUrl["kind"],
  protocols: ProtocolKind[],
) {
  const protocol = endpointProtocolByKind[kind];
  return (
    kind !== "models" &&
    (protocol === undefined || protocols.includes(protocol))
  );
}

/** Converts a persisted site into channel editor state. */
export function toForm(site: Site): FormState {
  const baseUrls: FormBaseUrl[] = site.base_urls.length
    ? site.base_urls.map((item) => ({
        id: item.id,
        url: item.url,
        kind: item.kind ?? (item === site.base_urls[0] ? "default" : "china"),
      }))
    : [
        {
          id: createLocalId("baseurl"),
          url: "",
          kind: "default",
        },
      ];
  const credentials: FormCredential[] = site.credentials.map((item) => ({
    id: persistedCredentialId(item.id),
    name: isGeneratedCredentialName(item.name) ? "" : item.name,
    api_key: item.api_key,
    model_pattern: item.model_pattern ?? "",
    rate_source: item.rate_source,
    rate_protocol_config_id: item.rate_protocol_config_id,
    rate_group: item.rate_group,
    rate_multiplier: item.rate_multiplier,
    rate_observed_at: item.rate_observed_at,
    rate_last_synced_at: item.rate_last_synced_at,
    rate_last_error: item.rate_last_error,
    base_url_ids: item.base_url_ids,
  }));
  const protocolConfigs = site.protocols.map((protocolConfig) => {
    const models = coalesceFormModels(
      protocolConfig.models.map((model) => ({
        protocols: model.protocol ? [model.protocol] : [],
        modelIdsByProtocol: model.protocol
          ? { [model.protocol]: model.id }
          : {},
        credential_id: persistedCredentialId(model.credential_id),
        model_name: model.model_name,
        enabled: model.enabled,
        context_window: model.context_window,
        upstream_context_window: model.upstream_context_window,
      })),
    );
    const credentialIds = canonicalizeCredentialIds(
      protocolConfig.credential_ids.map(persistedCredentialId),
    );
    return {
      id: protocolConfig.id,
      base_url_id: protocolConfig.base_url_id,
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
  };
  return {
    ...draft,
    protocolConfigs: rebuildProtocolConfigs(draft),
  };
}

/** Prepare base URLs for the site payload. */
export function formBaseUrlsForPayload(form: FormState) {
  return form.base_urls
    .map((item) => ({
      id: item.id,
      url: item.url.trim(),
      kind: item.kind,
    }))
    .filter((item) => item.url);
}

/** Converts channel editor state into a site payload. */
export function toPayload(form: FormState): SitePayload {
  const drafted = applyApiKeyDrafts(form);
  const rebuilt = {
    ...drafted,
    protocolConfigs: rebuildProtocolConfigs(drafted),
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
    base_urls: baseUrls,
    credentials: credentials.map((item, index) => ({
      id: persistedCredentialId(item.id),
      name: item.name.trim() || fallbackCredentialName(index),
      api_key: item.api_key.trim(),
      base_url_ids: item.base_url_ids,
      model_pattern: item.model_pattern.trim(),
      rate_source: item.rate_source,
      rate_protocol_config_id:
        item.rate_source === "none" ? "" : item.rate_protocol_config_id,
      rate_group: item.rate_group.trim(),
    })),
    protocols: rebuilt.protocolConfigs.flatMap((protocolConfig) => {
      const models = protocolConfig.models
        .flatMap((model) =>
          model.protocols.map((protocol) => ({
            id: model.modelIdsByProtocol[protocol] ?? null,
            protocol,
            credential_id: persistedCredentialId(model.credential_id),
            model_name: model.model_name.trim(),
            enabled: model.enabled,
            context_window: model.context_window,
            upstream_context_window: model.upstream_context_window,
          })),
        )
        .filter((model) => model.credential_id && model.model_name);
      return [
        {
          id: protocolConfig.id,
          base_url_id: protocolConfig.base_url_id,
          protocols: protocolConfig.protocols,
          models,
        },
      ];
    }),
  };
}
