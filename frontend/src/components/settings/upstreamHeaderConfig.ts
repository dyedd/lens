import { type Locale, titleForLocale } from "@/lib/I18nContext";
import {
  EMPTY_HEADER_RULE,
  type HeaderRuleDraft,
  headerDraftToRules,
  type UpstreamHeadersDraft,
} from "@/lib/upstreamRules";

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

export type HeaderItem = HeaderRuleDraft;
export type { UpstreamHeadersDraft };

const EMPTY_HEADERS: HeaderItem[] = [EMPTY_HEADER_RULE];

export function parseHeaderRows(value: unknown): HeaderItem[] {
  if (!Array.isArray(value)) return [...EMPTY_HEADERS];
  const rows = value
    .filter(isRecord)
    .map((item) => ({
      key: typeof item.name === "string" ? item.name : "",
      value:
        typeof item.value === "string" ? item.value : String(item.value ?? ""),
      action: (item.action === "remove" || item.action === "append"
        ? item.action
        : "override") as HeaderItem["action"],
    }))
    .filter((item) => item.key.trim());
  return rows.length ? rows : [...EMPTY_HEADERS];
}

export function headersToRules(headers: HeaderItem[]) {
  return headerDraftToRules(headers);
}

function hasHeaderValueWithoutKey(headers: HeaderItem[]) {
  return headers.some((header) => header.value.trim() && !header.key.trim());
}

export function createEmptyUpstreamHeadersDraft(): UpstreamHeadersDraft {
  return { rules: [...EMPTY_HEADERS] };
}

export function parseUpstreamHeadersConfig(
  rawValue: string | undefined,
): UpstreamHeadersDraft {
  if (!rawValue?.trim()) return createEmptyUpstreamHeadersDraft();
  const payload = parseJsonObject(rawValue);
  return {
    rules: parseHeaderRows(payload?.rules),
  };
}

export function serializeUpstreamHeadersConfig(config: UpstreamHeadersDraft) {
  return JSON.stringify({ rules: headersToRules(config.rules) });
}

export function validateUpstreamHeadersConfig(
  config: UpstreamHeadersDraft,
  locale: Locale,
) {
  if (hasHeaderValueWithoutKey(config.rules)) {
    return titleForLocale(
      locale,
      "请求头名称不能为空。",
      "Header names are required.",
    );
  }
  return null;
}
