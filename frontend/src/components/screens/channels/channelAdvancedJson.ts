import {
  type HeaderRuleDraft,
  headerDraftToRules,
  headerRulesToDraft,
  isHeaderRule,
  isParamOverrideRule,
  type ParamOverrideRuleDraft,
  paramOverrideDraftToRules,
  paramOverrideRulesToDraft,
} from "@/lib/upstreamRules";

type JsonRecord = Record<string, unknown>;

function parseRuleJson(
  raw: string,
): JsonRecord | unknown[] | "empty" | "invalid" {
  if (!raw.trim()) return "empty";
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed === null || typeof parsed !== "object") return "invalid";
    return parsed as JsonRecord | unknown[];
  } catch {
    return "invalid";
  }
}

function stringifyRuleJson(value: JsonRecord | unknown[]): string {
  return Object.keys(value).length ? JSON.stringify(value, null, 2) : "";
}

export function headerDraftsToJson(drafts: HeaderRuleDraft[]): string {
  const rules = headerDraftToRules(drafts);
  // 条件、动作和同名规则的顺序不能用键值对象表达。
  if (
    rules.some((rule) => rule.action !== "override" || rule.match) ||
    new Set(rules.map((rule) => rule.name)).size !== rules.length
  ) {
    return stringifyRuleJson(rules);
  }
  return stringifyRuleJson(
    Object.fromEntries(rules.map((rule) => [rule.name, rule.value])),
  );
}

export function headerDraftsFromJson(raw: string): HeaderRuleDraft[] | null {
  const parsed = parseRuleJson(raw);
  if (parsed === "invalid") return null;
  if (parsed === "empty") return [];
  if (Array.isArray(parsed)) {
    return parsed.every(isHeaderRule) ? headerRulesToDraft(parsed) : null;
  }
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

export function paramDraftsToJson(drafts: ParamOverrideRuleDraft[]): string {
  const rules = paramOverrideDraftToRules(drafts);
  if (
    rules.some((rule) => rule.action === "delete") ||
    new Set(rules.map((rule) => rule.path)).size !== rules.length
  ) {
    return stringifyRuleJson(rules);
  }
  return stringifyRuleJson(
    Object.fromEntries(rules.map((rule) => [rule.path, rule.value])),
  );
}

export function paramDraftsFromJson(
  raw: string,
): ParamOverrideRuleDraft[] | null {
  const parsed = parseRuleJson(raw);
  if (parsed === "invalid") return null;
  if (parsed === "empty") return [];
  if (Array.isArray(parsed)) {
    return parsed.every(isParamOverrideRule)
      ? paramOverrideRulesToDraft(parsed)
      : null;
  }
  return Object.entries(parsed).map(([path, value]) => ({
    path,
    action: "set",
    value: JSON.stringify(value),
  }));
}

export function mergeHeaderJson(
  raw: string,
  extra: Record<string, string>,
): string | null {
  const drafts = headerDraftsFromJson(raw);
  if (drafts === null) return null;
  for (const [name, value] of Object.entries(extra)) {
    const existing = drafts.find(
      (rule) => rule.key === name && rule.action === "override" && !rule.match,
    );
    if (existing) existing.value = value;
    else drafts.push({ key: name, value, action: "override" });
  }
  return headerDraftsToJson(drafts);
}
