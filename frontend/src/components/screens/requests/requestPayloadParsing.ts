export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

/** Parse a JSON value and return null when parsing fails. */
export function tryParseJsonValue(value: string) {
  try {
    return JSON.parse(value) as JsonValue;
  } catch {
    return null;
  }
}

export function formatHtmlErrorContent(value: string) {
  return value
    .replace(/>\s*</g, ">\n<")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(
      /<\/(p|div|section|article|header|footer|main|h1|h2|h3|h4|h5|h6|li|ul|ol|pre|code)>/gi,
      "$&\n",
    )
    .trim();
}

export function formatJsonErrorContent(prefix: string, value: JsonValue) {
  const jsonText = JSON.stringify(value, null, 2);
  if (!jsonText) return prefix.trim() || null;
  return jsonText;
}

/** Extract the first string value of common error shapes, or null. */
function knownErrorMessage(value: JsonValue): string | null {
  if (typeof value === "string") return value;
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const container =
    typeof value.error === "object" &&
    value.error !== null &&
    !Array.isArray(value.error)
      ? value.error
      : value;
  for (const key of ["message", "msg", "detail", "error"]) {
    const candidate = container[key];
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }
  return null;
}

/** Parse a payload as JSON, tolerating a text prefix before the object. */
function parseErrorJson(raw: string): JsonValue | null {
  const direct = tryParseJsonValue(raw);
  if (direct !== null) return direct;
  const jsonStart = raw.indexOf("{");
  if (jsonStart > 0) return tryParseJsonValue(raw.slice(jsonStart));
  return null;
}

/** Collapse a JSON or text error into a single display line. */
export function formatErrorSummary(value: string | null | undefined) {
  const raw = value?.trim();
  if (!raw) return null;
  const known = knownErrorMessage(parseErrorJson(raw));
  if (known) return known;
  const display = formatErrorDisplay(value);
  if (!display) return null;
  if (!display.includes("\n")) return display;
  return (
    display
      .split("\n")
      .map((line) => line.trim())
      .find(Boolean) || display
  );
}

/** Format JSON, HTML, or text errors for readable display. */
export function formatErrorDisplay(value: string | null | undefined) {
  const raw = value?.trim();
  if (!raw) return null;

  const directParsed = tryParseJsonValue(raw);
  if (directParsed !== null) return formatJsonErrorContent("", directParsed);

  const jsonStart = raw.indexOf("{");
  if (jsonStart > 0) {
    const nestedParsed = tryParseJsonValue(raw.slice(jsonStart));
    if (nestedParsed !== null) {
      return formatJsonErrorContent(raw.slice(0, jsonStart), nestedParsed);
    }
  }

  if (/<!doctype html|<html|<head|<body|<title/i.test(raw)) {
    return formatHtmlErrorContent(raw);
  }
  return raw;
}
