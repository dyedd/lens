export type ParamOverrideRule = {
  path: string;
  action: "set" | "delete";
  value: string;
};

export interface UpstreamParamOverrideDraft {
  rules: ParamOverrideRule[];
}
