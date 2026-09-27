import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api/client";
import type { RegexRule, RegexRuleRequest } from "@/lib/api/regexRules";

const NO_RULES: RegexRule[] = [];
// Rule edits and deletes change group membership and site references.
const RULE_DEPENDENT_QUERY_KEYS = [
  ["regex-rules"],
  ["groups"],
  ["group-candidates"],
  ["sites"],
] as const;

/** Load the regex rule library and write rules through to every reference. */
export function useRegexRules() {
  const queryClient = useQueryClient();
  const rulesQuery = useQuery({
    queryKey: ["regex-rules"],
    queryFn: () => apiRequest<RegexRule[]>("/admin/regex-rules"),
    // Usage lists change whenever a site or group is saved anywhere.
    refetchOnMount: "always",
  });

  function applyRuleChange(update: (rules: RegexRule[]) => RegexRule[]) {
    queryClient.setQueryData<RegexRule[]>(["regex-rules"], (current) =>
      update(current ?? []),
    );
    for (const queryKey of RULE_DEPENDENT_QUERY_KEYS) {
      void queryClient.invalidateQueries({ queryKey });
    }
  }

  async function createRule(request: RegexRuleRequest) {
    const rule = await apiRequest<RegexRule>("/admin/regex-rules", {
      method: "POST",
      body: JSON.stringify(request),
    });
    applyRuleChange((rules) => [...rules, rule]);
    return rule;
  }

  async function updateRule(ruleId: string, request: RegexRuleRequest) {
    const rule = await apiRequest<RegexRule>(`/admin/regex-rules/${ruleId}`, {
      method: "PUT",
      body: JSON.stringify(request),
    });
    applyRuleChange((rules) =>
      rules.map((item) => (item.id === rule.id ? rule : item)),
    );
    return rule;
  }

  async function deleteRule(ruleId: string) {
    await apiRequest<void>(`/admin/regex-rules/${ruleId}`, {
      method: "DELETE",
    });
    applyRuleChange((rules) => rules.filter((item) => item.id !== ruleId));
  }

  return {
    rules: rulesQuery.data ?? NO_RULES,
    isLoaded: rulesQuery.isSuccess,
    isError: rulesQuery.isError,
    createRule,
    updateRule,
    deleteRule,
  };
}
