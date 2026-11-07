export type HeaderRuleAction = "remove" | "override" | "append";

/** Persisted upstream request-header rule shared by sites and model groups. */
export type HeaderRule = {
  name: string;
  action: HeaderRuleAction;
  value: string;
  match?: {
    path_regex?: string | null;
    model_regex?: string | null;
    protocol_regex?: string | null;
  } | null;
};

/** Persisted upstream parameter rule shared by sites and model groups. */
export type ParamOverrideRule = {
  path: string;
  action: "set" | "delete";
  value?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isHeaderRule(value: unknown): value is HeaderRule {
  if (!isRecord(value)) return false;
  const match = value.match;
  return (
    typeof value.name === "string" &&
    typeof value.value === "string" &&
    (value.action === "remove" ||
      value.action === "override" ||
      value.action === "append") &&
    (match == null ||
      (isRecord(match) &&
        Object.entries(match).every(
          ([key, pattern]) =>
            ["path_regex", "model_regex", "protocol_regex"].includes(key) &&
            (pattern === null || typeof pattern === "string"),
        )))
  );
}

export function isParamOverrideRule(
  value: unknown,
): value is ParamOverrideRule {
  return (
    isRecord(value) &&
    typeof value.path === "string" &&
    (value.action === "set" || value.action === "delete")
  );
}

export type HeaderRuleDraft = {
  key: string;
  value: string;
  action: HeaderRuleAction;
  match?: HeaderRule["match"];
};

export type ParamOverrideRuleDraft = {
  path: string;
  action: ParamOverrideRule["action"];
  value: string;
};

export type UpstreamHeadersDraft = { rules: HeaderRuleDraft[] };
export type UpstreamParamOverrideDraft = { rules: ParamOverrideRuleDraft[] };

export const EMPTY_HEADER_RULE: HeaderRuleDraft = {
  key: "",
  value: "",
  action: "override",
};

export const EMPTY_PARAM_OVERRIDE_RULE: ParamOverrideRuleDraft = {
  path: "",
  action: "set",
  value: "",
};

export function headerRulesToDraft(rules: HeaderRule[]): HeaderRuleDraft[] {
  const drafts = rules.map(({ name, value, action, match }) => ({
    key: name,
    value,
    action,
    match,
  }));
  return drafts.length ? drafts : [{ ...EMPTY_HEADER_RULE }];
}

export function headerDraftToRules(drafts: HeaderRuleDraft[]): HeaderRule[] {
  return drafts
    .filter((rule) => rule.key.trim())
    .map((rule) => ({
      name: rule.key.trim(),
      action: rule.action,
      value: rule.action === "remove" ? rule.value.trim() : rule.value,
      match: rule.match,
    }));
}

export function paramOverrideRulesToDraft(
  rules: ParamOverrideRule[],
): ParamOverrideRuleDraft[] {
  const drafts = rules.map((rule) => ({
    path: rule.path,
    action: rule.action,
    value: rule.value === undefined ? "" : JSON.stringify(rule.value),
  }));
  return drafts.length ? drafts : [{ ...EMPTY_PARAM_OVERRIDE_RULE }];
}

export function parseParamRuleValue(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

export function paramOverrideDraftToRules(
  drafts: ParamOverrideRuleDraft[],
): ParamOverrideRule[] {
  return drafts
    .filter((rule) => rule.path.trim())
    .map((rule) => ({
      path: rule.path.trim(),
      action: rule.action,
      ...(rule.action === "set"
        ? { value: parseParamRuleValue(rule.value) }
        : {}),
    }));
}
