import type { ProtocolKind } from "@/lib/api";
import type {
  FormModel,
  FormProtocolConfig,
  FormSyncTarget,
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
export function replaceSyncedModels(
  models: FormModel[],
  syncTargets: FormSyncTarget[],
  fetched: PickerModelItem[],
  protocols: ProtocolKind[],
) {
  const selectedProtocols = Array.from(new Set(protocols));
  const fetchedKeys = new Set(fetched.map(genericModelKey));
  const coveredCredentialIds = new Set(
    fetched.map((item) => item.credential_id),
  );
  const manualKeys = new Set(
    models.filter((model) => model.source === "manual").map(genericModelKey),
  );
  const resetModel = (model: FormModel) =>
    model.source === "synced" && coveredCredentialIds.has(model.credential_id);
  const retainedSynced = models.flatMap((model) => {
    if (!resetModel(model)) return [model];
    const retainedProtocols = model.protocols.filter(
      (protocol) => !selectedProtocols.includes(protocol),
    );
    return retainedProtocols.length
      ? [
          {
            ...model,
            protocols: retainedProtocols,
            protocolIds: Object.fromEntries(
              retainedProtocols.map((protocol) => [
                protocol,
                model.protocolIds[protocol],
              ]),
            ),
          },
        ]
      : [];
  });
  const priorSynced = new Map(
    models
      .filter((model) => model.source === "synced")
      .map((model) => [genericModelKey(model), model]),
  );
  const nextModels = [...retainedSynced];
  for (const item of fetched) {
    const key = genericModelKey(item);
    if (manualKeys.has(key)) continue;
    const previous = priorSynced.get(key);
    nextModels.push({
      ...previous,
      protocols: selectedProtocols,
      protocolIds: previous
        ? Object.fromEntries(
            Object.entries(previous.protocolIds).filter(([protocol]) =>
              selectedProtocols.includes(protocol as ProtocolKind),
            ),
          )
        : {},
      credential_id: item.credential_id,
      model_name: item.model_name,
      enabled: true,
      source: "synced",
    });
  }
  const nextTargets = syncTargets.filter(
    (target) =>
      !(
        coveredCredentialIds.has(target.credential_id) &&
        selectedProtocols.includes(target.protocol)
      ),
  );
  for (const item of fetched) {
    if (manualKeys.has(genericModelKey(item))) continue;
    for (const protocol of selectedProtocols) {
      nextTargets.push({
        credential_id: item.credential_id,
        model_name: item.model_name,
        protocol,
      });
    }
  }
  return {
    models: coalesceFormModels(nextModels),
    syncTargets: nextTargets,
    removedCount: models.filter(
      (model) =>
        resetModel(model) &&
        model.protocols.some((protocol) =>
          selectedProtocols.includes(protocol),
        ) &&
        !fetchedKeys.has(genericModelKey(model)),
    ).length,
  };
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
  protocolConfig: Pick<
    FormProtocolConfig,
    "manual_protocols" | "models" | "sync_targets"
  >,
) {
  return Array.from(
    new Set([
      ...protocolConfig.manual_protocols,
      ...protocolConfig.models.flatMap((model) => model.protocols),
      ...protocolConfig.sync_targets.map((target) => target.protocol),
    ]),
  );
}
