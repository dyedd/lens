import type { ProtocolKind } from "@/lib/api";
import {
  protocolConfigSelectedCredentialIds,
  type FormProtocolConfig,
  type FormState,
} from "./channelShared";

const MODEL_ACTION_COOLDOWN_MS = 800;

export function canRunModelAction(
  lastRunAt: Record<string, number>,
  key: string,
) {
  const now = Date.now();
  if (now - (lastRunAt[key] ?? 0) < MODEL_ACTION_COOLDOWN_MS) return false;
  lastRunAt[key] = now;
  return true;
}

export function activeSelectedCredentialIds(
  form: FormState,
  config: FormProtocolConfig,
) {
  const credentials = new Map(
    form.credentials.map((credential) => [credential.id, credential]),
  );
  return protocolConfigSelectedCredentialIds(config).filter((id) => {
    const credential = credentials.get(id);
    return Boolean(credential?.enabled && credential.api_key.trim());
  });
}

export function buildManualModels(
  config: FormProtocolConfig,
  credentialIds: string[],
  modelName: string,
  protocols: ProtocolKind[],
) {
  const existing = new Set(
    config.models.map((model) => `${model.credential_id}:${model.model_name}`),
  );
  return credentialIds
    .filter((id) => !existing.has(`${id}:${modelName}`))
    .map((credentialId) => ({
      id: null,
      protocols,
      protocolIds: {},
      credential_id: credentialId,
      model_name: modelName,
      enabled: true,
    }));
}
