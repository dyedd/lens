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

export type HeaderRuleDraft = {
  key: string;
  value: string;
  action: HeaderRuleAction;
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
  const drafts = rules.map(({ name, value, action }) => ({
    key: name,
    value,
    action,
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
