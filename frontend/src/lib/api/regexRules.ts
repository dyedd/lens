/** A channel or model group that references a regex rule. */
export type RegexRuleReference = { id: string; name: string };

/** A named library pattern that channels and model groups reference by id. */
export type RegexRule = {
  id: string;
  name: string;
  pattern: string;
  description: string;
  sites: RegexRuleReference[];
  groups: RegexRuleReference[];
};

export type RegexRuleRequest = Pick<
  RegexRule,
  "name" | "pattern" | "description"
>;
