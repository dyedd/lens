/** Create a stable identifier for an editable upstream rule. */
export function createDraftId(prefix: string) {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return [prefix, Date.now(), Math.random().toString(16).slice(2)].join("-");
}

/** Format an object value for an editable JSON textarea. */
export function formatJsonObject(value: unknown): string {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return JSON.stringify(value, null, 2);
  }
  return "";
}

/** Return whether a value is a non-array object. */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/** Parse a JSON object, returning null for invalid or non-object values. */
export function parseJsonObject(
  rawValue: string,
): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(rawValue.trim());
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

/** Parse a comma- or line-separated model list without duplicates. */
export function parseModelListText(value: string) {
  const models: string[] = [];
  const seen = new Set<string>();
  for (const item of value.replaceAll("，", ",").split(/[\n,]/)) {
    const model = item.trim();
    if (!model || seen.has(model)) {
      continue;
    }
    seen.add(model);
    models.push(model);
  }
  return models;
}
