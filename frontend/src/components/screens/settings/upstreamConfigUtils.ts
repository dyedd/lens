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
