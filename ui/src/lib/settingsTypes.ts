export type ParamOverrideMatchType = "exact" | "regex";

export interface UpstreamParamOverrideRuleDraft {
  id: string;
  enabled: boolean;
  name: string;
  matchType: ParamOverrideMatchType;
  models: string;
  pattern: string;
  override: string;
}

export interface UpstreamParamOverrideDraft {
  global: string;
  rules: UpstreamParamOverrideRuleDraft[];
}
