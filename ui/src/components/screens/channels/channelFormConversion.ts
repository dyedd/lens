import type { ProtocolKind, Site, SitePayload } from "@/lib/api";
import type { Locale } from "@/lib/I18nContext";
import { isGeneratedCredentialName } from "@/lib/utils";
import { createLocalId } from "./channelDefaults";
import {
  normalizeCredentialIds,
  protocolConfigSelectedCredentialIds,
  resolveBaseUrlId,
} from "./channelFormUtils";
import {
  fallbackCredentialName,
  protocolConfigDisplayName,
} from "./channelLabels";
import {
  coalesceFormModels,
  protocolConfigEffectiveProtocols,
} from "./channelModelUtils";
import type { FormState } from "./channelTypes";

/** Converts a persisted site into channel editor state. */
export function toForm(site: Site, locale: Locale = "zh-CN"): FormState {
  const baseUrls = site.base_urls.length
    ? site.base_urls.map((item) => ({
        id: item.id,
        url: item.url,
        name: item.name,
        enabled: item.enabled,
        supported_protocols: item.supported_protocols,
      }))
    : [
        {
          id: createLocalId("baseurl"),
          url: "",
          name: "",
          enabled: true,
          supported_protocols: [] as ProtocolKind[],
        },
      ];
  const credentials = site.credentials.map((item) => ({
    id: item.id,
    name: isGeneratedCredentialName(item.name) ? "" : item.name,
    api_key: item.api_key,
    enabled: item.enabled,
  }));
  return {
    name: site.name,
    base_urls: baseUrls,
    credentials,
    protocolConfigs: site.protocols.map(
      (protocolConfig, protocolConfigIndex) => {
        const models = coalesceFormModels(
          protocolConfig.models.map((model) => ({
            protocols: model.protocol ? [model.protocol] : [],
            protocolIds: model.protocol ? { [model.protocol]: model.id } : {},
            credential_id: model.credential_id,
            model_name: model.model_name,
            enabled: model.enabled,
            source: model.source,
          })),
        );
        const credentialIds = normalizeCredentialIds(
          protocolConfig.credential_ids,
        );
        return {
          id: protocolConfig.id,
          name: protocolConfigDisplayName(
            protocolConfig,
            protocolConfigIndex,
            locale,
          ),
          enabled: protocolConfig.enabled,
          headers: Object.entries(protocolConfig.headers).length
            ? Object.entries(protocolConfig.headers).map(([key, value]) => ({
                key,
                value,
              }))
            : [{ key: "", value: "" }],
          proxy_mode: protocolConfig.proxy_mode,
          channel_proxy: protocolConfig.channel_proxy,
          param_override: protocolConfig.param_override,
          model_filter: "",
          sync_new_models: false,
          manual_model_name: "",
          manual_protocols: Array.from(new Set(protocolConfig.protocols)),
          base_url_id: resolveBaseUrlId(baseUrls, protocolConfig.base_url_id),
          credential_ids: credentialIds,
          sync_targets: protocolConfig.sync_targets,
          models,
          expanded: models.length === 0,
        };
      },
    ),
  };
}

export function baseUrlProtocolMap(form: FormState) {
  const map = new Map<string, Set<ProtocolKind>>();
  for (const baseUrl of form.base_urls) {
    map.set(baseUrl.id, new Set());
  }
  for (const protocolConfig of form.protocolConfigs) {
    const protocols = protocolConfigEffectiveProtocols(protocolConfig);
    const set = map.get(protocolConfig.base_url_id);
    if (!set) continue;
    protocols.forEach((protocol) => set.add(protocol));
  }
  return map;
}

/** Normalizes non-empty base URLs and derives their supported protocols. */
export function formBaseUrlsForPayload(form: FormState) {
  const protocolsByBaseUrl = baseUrlProtocolMap(form);
  return form.base_urls
    .map((item) => ({
      id: item.id,
      url: item.url.trim(),
      name: item.name.trim(),
      enabled: item.enabled,
      supported_protocols: Array.from(protocolsByBaseUrl.get(item.id) ?? []),
    }))
    .filter((item) => item.url);
}

/** Converts channel editor state into a normalized site payload. */
export function toPayload(form: FormState): SitePayload {
  const baseUrls = formBaseUrlsForPayload(form);
  return {
    name: form.name.trim(),
    base_urls: baseUrls,
    credentials: form.credentials
      .map((item, index) => ({
        id: item.id,
        name: item.name.trim() || fallbackCredentialName(index),
        api_key: item.api_key.trim(),
        enabled: item.enabled,
      }))
      .filter((item) => item.api_key),
    protocols: form.protocolConfigs.map((protocolConfig) => {
      const selectedCredentialIds =
        protocolConfigSelectedCredentialIds(protocolConfig);
      const protocolConfigProtocols =
        protocolConfigEffectiveProtocols(protocolConfig);
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
            credential_id: model.credential_id,
            model_name: model.model_name.trim(),
            enabled: model.enabled,
            source: model.source,
          }));
        })
        .filter((model) => model.credential_id && model.model_name);
      const syncTargets = protocolConfig.sync_targets
        .filter(
          (target) =>
            selectedCredentialIds.includes(target.credential_id) &&
            protocolConfigProtocols.includes(target.protocol) &&
            target.model_name.trim(),
        )
        .map((target) => ({
          ...target,
          model_name: target.model_name.trim(),
        }));
      return {
        id: protocolConfig.id,
        name: protocolConfig.name.trim(),
        protocols: protocolConfigProtocols,
        enabled: protocolConfig.enabled,
        headers: Object.fromEntries(
          protocolConfig.headers
            .map((entry) => [entry.key.trim(), entry.value] as const)
            .filter(([key]) => key),
        ),
        proxy_mode: protocolConfig.proxy_mode,
        channel_proxy: protocolConfig.channel_proxy.trim(),
        param_override: protocolConfig.param_override.trim(),
        base_url_id: protocolConfig.base_url_id,
        credential_ids: selectedCredentialIds,
        sync_targets: syncTargets,
        models,
      };
    }),
  };
}
