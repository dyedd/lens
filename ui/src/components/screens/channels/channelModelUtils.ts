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
