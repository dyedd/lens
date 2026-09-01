import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  FormModel,
  FormProtocolConfig,
  FormSyncTarget,
  PickerModelItem,
} from "./channelTypes";

export function syncTargetKey(target: FormSyncTarget) {
  return JSON.stringify([
    target.credential_id,
    target.model_name,
    target.protocol,
  ]);
}

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

/** Builds the collapsed overview row key shared by same-name models. */
export function aggregateModelGroupKey(
  protocolConfig: Pick<FormProtocolConfig, "id">,
  modelName: string,
) {
  return JSON.stringify([protocolConfig.id, modelName]);
}

/** Reports whether a key targets a whole model group instead of one model. */
export function isAggregateModelGroupKey(key: string) {
  // Group keys hold two JSON parts; model keys hold four.
  return key.startsWith("[") && key.split(",").length === 2;
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

/** Groups picker rows by model name so one choice can cover every key. */
export function groupPickerModelsByName(models: PickerModelItem[]) {
  const groups = new Map<string, PickerModelItem[]>();
  for (const model of groupPickerModels(models)) {
    const items = groups.get(model.model_name);
    if (items) {
      items.push(model);
      continue;
    }
    groups.set(model.model_name, [model]);
  }
  return Array.from(groups, ([model_name, items]) => ({
    model_name,
    items,
  }));
}

/** Reports whether a picker model has an explicit protocol override. */
export function hasPickerModelProtocolOverride(
  overrides: Record<string, ProtocolKind[]>,
  key: string,
) {
  return Object.hasOwn(overrides, key);
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

/** Returns the unique protocols supported by a form model. */
export function modelSupportedProtocols(
  model: Pick<FormModel, "protocols"> | null | undefined,
) {
  if (model?.protocols && model.protocols.length > 0) {
    return Array.from(new Set(model.protocols));
  }
  return [];
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
