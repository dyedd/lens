import { toast } from "sonner";
import type {
  ModelGroup,
  ModelGroupEnsureFromSiteResponse,
  ModelGroupEnsureModelInput,
  Site,
} from "@/lib/api";
import {
  modelGroupEnsureSkippedToastMessage,
  suggestModelGroupName,
} from "./modelGroupEnsure";

/** Builds enabled, uniquely addressable models for group ensure requests. */
export function buildModelGroupEnsureInputs(
  site: Site,
  groups: ModelGroup[],
): ModelGroupEnsureModelInput[] {
  const baseUrlIds = new Set(
    site.base_urls
      .filter((item) => item.enabled && item.url.trim())
      .map((item) => item.id),
  );
  const credentialIds = new Set(
    site.credentials
      .filter((item) => item.enabled && item.api_key.trim())
      .map((item) => item.id),
  );
  const models = new Map<string, ModelGroupEnsureModelInput>();
  for (const config of site.protocols) {
    if (!config.enabled || !baseUrlIds.has(config.base_url_id)) continue;
    const configuredProtocols = new Set(config.protocols);
    for (const model of config.models) {
      const modelName = model.model_name.trim();
      if (
        !model.enabled ||
        !modelName ||
        !model.protocol ||
        !configuredProtocols.has(model.protocol) ||
        !credentialIds.has(model.credential_id)
      ) {
        continue;
      }
      const key = JSON.stringify([config.id, model.credential_id, modelName]);
      const current = models.get(key);
      if (current) {
        if (!current.protocols.includes(model.protocol)) {
          current.protocols.push(model.protocol);
        }
      } else {
        models.set(key, {
          protocol_config_id: config.id,
          credential_id: model.credential_id,
          model_name: modelName,
          group_name: suggestModelGroupName(modelName, groups),
          protocols: [model.protocol],
        });
      }
    }
  }
  return Array.from(models.values());
}

export function showModelGroupEnsureSkippedToast(
  result: ModelGroupEnsureFromSiteResponse,
  locale: string,
) {
  const message = modelGroupEnsureSkippedToastMessage(result, locale);
  if (message) toast.warning(message);
}
