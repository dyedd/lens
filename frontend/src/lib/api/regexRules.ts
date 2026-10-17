/** A model group or site that references a regex rule. */
export type RegexRuleReference = { id: string; name: string };

/** A named library pattern that model groups and sites reference by id. */
export type RegexRule = {
  id: string;
  name: string;
  pattern: string;
  description: string;
  /** Groups whose members are matched by the rule instead of the group name. */
  groups: RegexRuleReference[];
  /** Sites referencing the rule as onboarding or exclusion filter. */
  sites: RegexRuleReference[];
};

export type RegexRuleRequest = Pick<
  RegexRule,
  "name" | "pattern" | "description"
>;
