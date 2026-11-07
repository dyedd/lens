import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  FormModel,
  FormProtocolConfig,
  PickerModelItem,
} from "./channelTypes";

export function modelSourceKey(item: Omit<PickerModelItem, "context_window">) {
  return JSON.stringify([
    item.protocol_config_id,
    item.credential_id,
    item.model_name,
    item.protocol,
  ]);
}

/** Builds a stable model key scoped to a protocol configuration. */
export function protocolConfigModelKey(
  protocolConfig: Pick<FormProtocolConfig, "id">,
  model: Pick<FormModel, "credential_id" | "model_name">,
) {
  return JSON.stringify([
    protocolConfig.id,
    model.credential_id,
    model.model_name,
  ]);
}

/** 同一渠道的同名模型共用一行，具体出口和 Key 保留各自记录。 */
export function aggregateModelGroupKey(modelName: string) {
  return JSON.stringify(["model", modelName]);
}

/** Merges form models that represent the same persisted model rows. */
export function coalesceFormModels(models: FormModel[]) {
  const groups = new Map<string, FormModel>();
  for (const model of models) {
    const key = JSON.stringify([model.credential_id, model.model_name]);
    const existing = groups.get(key);
    if (!existing) {
      groups.set(key, {
        ...model,
        protocols: Array.from(new Set(model.protocols)),
        modelIdsByProtocol: { ...model.modelIdsByProtocol },
      });
      continue;
    }
    existing.protocols = Array.from(
      new Set([...existing.protocols, ...model.protocols]),
    );
    existing.modelIdsByProtocol = {
      ...existing.modelIdsByProtocol,
      ...model.modelIdsByProtocol,
    };
    existing.enabled = existing.enabled || model.enabled;
    existing.context_window ??= model.context_window;
    existing.upstream_context_window ??= model.upstream_context_window;
  }
  return Array.from(groups.values());
}

/** Returns the unique protocols supported by a form model. */
export function modelSupportedProtocols(
  model: Pick<FormModel, "protocols"> | null | undefined,
): ProtocolKind[] {
  if (model?.protocols && model.protocols.length > 0) {
    return Array.from(new Set(model.protocols));
  }
  return [];
}

export function protocolConfigEffectiveProtocols(
  protocolConfig: Pick<FormProtocolConfig, "models">,
): ProtocolKind[] {
  return Array.from(
    new Set(protocolConfig.models.flatMap((model) => model.protocols)),
  );
}

/** Builds the whole-name filter that selects exactly this model. */
export function escapeModelName(modelName: string) {
  return `^${modelName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`;
}

/** Appends exact-name filters to a key's pattern, skipping ones it has. */
export function mergeModelPatterns(
  current: string,
  additions: string[],
): string {
  // 后端始终忽略大小写；把标记包进分支会让 Python 拒绝合并后的表达式。
  const existing = current
    .trim()
    .replace(/^\(\?[aiLmsux]+\)/, "")
    .trim();
  if (existing === "*") return existing;
  const fresh = additions
    .map((addition) => addition.trim())
    .filter((addition) => addition && !existing.includes(addition));
  if (!fresh.length) return existing;
  // 当前规则包成一个分支，避免已有的 `|` 吞掉追加的模型名。
  return [existing ? `(?:${existing})` : "", ...fresh]
    .filter(Boolean)
    .join("|");
}
