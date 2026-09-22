import type {
  HeaderRuleDraft,
  ParamOverrideRuleDraft,
} from "@/lib/upstreamRules";

type JsonRecord = Record<string, unknown>;

function parseJsonRecord(raw: string): JsonRecord | "empty" | "invalid" {
  const trimmed = raw.trim();
  if (!trimmed) return "empty";
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (
      parsed === null ||
      Array.isArray(parsed) ||
      typeof parsed !== "object"
    ) {
      return "invalid";
    }
    return parsed as JsonRecord;
  } catch {
    return "invalid";
  }
}

function stringifyJsonRecord(value: JsonRecord): string {
  return Object.keys(value).length ? JSON.stringify(value, null, 2) : "";
}

/** Serializes override header drafts as a JSON object. */
export function headerDraftsToJson(rules: HeaderRuleDraft[]): string {
  const value: Record<string, string> = {};
  for (const rule of rules) {
    const name = rule.key.trim();
    if (!name || rule.action === "remove") continue;
    value[name] = rule.value;
  }
  return stringifyJsonRecord(value);
}

/** Parses a JSON object into override header drafts. */
export function headerDraftsFromJson(raw: string): HeaderRuleDraft[] | null {
  const parsed = parseJsonRecord(raw);
  if (parsed === "invalid") return null;
  if (parsed === "empty") return [];
  const drafts: HeaderRuleDraft[] = [];
  for (const [key, value] of Object.entries(parsed)) {
    if (
      typeof value !== "string" &&
      typeof value !== "number" &&
      typeof value !== "boolean"
    ) {
      return null;
    }
    drafts.push({ key, value: String(value), action: "override" });
  }
  return drafts;
}

/** Serializes set-parameter drafts as a JSON object. */
export function paramDraftsToJson(rules: ParamOverrideRuleDraft[]): string {
  const value: JsonRecord = {};
  for (const rule of rules) {
    const path = rule.path.trim();
    if (!path || rule.action === "delete") continue;
    if (!rule.value.trim()) continue;
    try {
      value[path] = JSON.parse(rule.value) as unknown;
    } catch {
      value[path] = rule.value;
    }
  }
  return stringifyJsonRecord(value);
}

/** Parses a JSON object into set-parameter drafts. */
export function paramDraftsFromJson(
  raw: string,
): ParamOverrideRuleDraft[] | null {
  const parsed = parseJsonRecord(raw);
  if (parsed === "invalid") return null;
  if (parsed === "empty") return [];
  return Object.entries(parsed).map(([path, value]) => ({
    path,
    action: "set",
    value: value === undefined ? "" : JSON.stringify(value),
  }));
}

/** Merges header presets into a JSON object, or null when the draft is invalid. */
export function mergeHeaderJson(
  raw: string,
  extra: Record<string, string>,
): string | null {
  const parsed = parseJsonRecord(raw);
  if (parsed === "invalid") return null;
  const value: JsonRecord = parsed === "empty" ? {} : { ...parsed };
  for (const [name, headerValue] of Object.entries(extra)) {
    value[name] = headerValue;
  }
  return stringifyJsonRecord(value);
}
