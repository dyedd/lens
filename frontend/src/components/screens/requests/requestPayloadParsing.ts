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
