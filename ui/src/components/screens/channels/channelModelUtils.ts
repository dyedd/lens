import type { ProtocolKind } from "@/lib/api";
import type {
  FormModel,
  FormProtocolConfig,
  PickerModelItem,
} from "./channelTypes";

/** Builds a model key scoped by credential and model name. */
export function genericModelKey(
  model: Pick<PickerModelItem, "credential_id" | "model_name">,
) {
  return `${model.credential_id}:${model.model_name}`;
}

/** Builds a stable model key scoped to a protocol configuration. */
export function protocolConfigModelKey(
  protocolConfig: Pick<FormProtocolConfig, "id">,
  model: Pick<FormModel, "credential_id" | "model_name" | "source">,
) {
  return JSON.stringify([
    protocolConfig.id,
    model.credential_id,
    model.model_name,
    model.source,
  ]);
}

/** Merges form models that represent the same persisted model rows. */
export function coalesceFormModels(models: FormModel[]) {
  const groups = new Map<string, FormModel>();
  for (const model of models) {
    const key = JSON.stringify([
      model.credential_id,
      model.model_name,
      model.source,
    ]);
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
  }
  return Array.from(groups.values());
}

/** Deduplicates picker models by credential and model name. */
export function groupPickerModels(models: PickerModelItem[]) {
  const groups = new Map<string, PickerModelItem>();
  for (const model of models) {
    const key = genericModelKey(model);
    if (groups.has(key)) {
      continue;
    }
    groups.set(key, {
      credential_id: model.credential_id,
      credential_name: model.credential_name,
      model_name: model.model_name,
    });
  }
  return Array.from(groups.values());
}

/** Reports whether a picker model has an explicit protocol override. */
export function hasPickerModelProtocolOverride(
  overrides: Record<string, ProtocolKind[]>,
  key: string,
) {
  return Object.prototype.hasOwnProperty.call(overrides, key);
}

/** Resolves picker protocols from an override or the shared fallback. */
export function resolvePickerModelProtocols(
  key: string,
  overrides: Record<string, ProtocolKind[]>,
  fallback: ProtocolKind[],
) {
  return hasPickerModelProtocolOverride(overrides, key)
    ? (overrides[key] ?? [])
    : fallback;
}

export function pickerModelKeys(models: PickerModelItem[]) {
  return Array.from(new Set(models.map((item) => genericModelKey(item))));
}

/**
 * Replaces the synced model set with what the upstream returned.
 *
 * Fetched models become synced, keeping the protocols and persisted ids of any
 * row they replace. Synced models the upstream no longer returns are dropped,
 * so narrowing the filter prunes them. Manual models are never touched, and
 * credentials absent from the response are skipped entirely so a partially
 * failed discovery cannot wipe a working credential's models.
 *
 * ``removedCount`` counts only pruned models, so callers do not mistake rows
 * merged by {@link coalesceFormModels} for upstream removals.
 */
export function mergeSyncedModels(
  models: FormModel[],
  fetched: PickerModelItem[],
  protocols: ProtocolKind[],
) {
  const fetchedKeys = new Set(fetched.map((item) => genericModelKey(item)));
  const coveredCredentialIds = new Set(
    fetched.map((item) => item.credential_id),
  );
  let removedCount = 0;
  const merged = models.flatMap((model) => {
    if (fetchedKeys.has(genericModelKey(model))) {
      return [{ ...model, source: "synced" as const }];
    }
    if (
      model.source === "synced" &&
      coveredCredentialIds.has(model.credential_id)
    ) {
      removedCount += 1;
      return [];
    }
    return [model];
  });
  const existingKeys = new Set(models.map((model) => genericModelKey(model)));
  for (const item of fetched) {
    if (existingKeys.has(genericModelKey(item))) continue;
    merged.push({
      protocols: Array.from(new Set(protocols)),
      protocolIds: {},
      credential_id: item.credential_id,
      model_name: item.model_name,
      enabled: true,
      source: "synced",
    });
  }
  return { models: coalesceFormModels(merged), removedCount };
}

/** Returns the unique protocols supported by a form model. */
export function modelSupportedProtocols(
  model: Pick<FormModel, "protocols"> | null | undefined,
) {
  if (model?.protocols && model.protocols.length > 0) {
    return Array.from(new Set(model.protocols));
  }
  return [];
}

/** Selects a valid test protocol with a deterministic fallback. */
export function selectedModelTestProtocol(
  protocols: ProtocolKind[],
  selectedProtocol: ProtocolKind | null,
) {
  return selectedProtocol && protocols.includes(selectedProtocol)
    ? selectedProtocol
    : (protocols[0] ?? null);
}

export function protocolConfigEffectiveProtocols(
  protocolConfig: Pick<FormProtocolConfig, "manual_protocols" | "models">,
) {
  return Array.from(
    new Set([
      ...protocolConfig.manual_protocols,
      ...protocolConfig.models.flatMap((model) => model.protocols),
    ]),
  );
}
