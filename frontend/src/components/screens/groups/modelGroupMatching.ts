import type { MatchRegexOperator } from "@/lib/api/groups";

/** Compile a rule pattern case-insensitively, or null when empty or invalid. */
export function compileRegexRulePattern(pattern: string) {
  const trimmedPattern = pattern.trim();
  // Python 的前置 (?i) 对应 JavaScript 的 i 标志。
  const source = trimmedPattern.startsWith("(?i)")
    ? trimmedPattern.slice(4)
    : trimmedPattern;
  if (!source) return null;
  try {
    return new RegExp(source, "i");
  } catch {
    return null;
  }
}

/** Match the group name and its optional local regex. */
export function matchesModelGroup(
  groupName: string,
  modelName: string,
  pattern: RegExp | null,
  operator: MatchRegexOperator = "or",
) {
  const nameMatches =
    Boolean(groupName.trim()) &&
    modelName.toLocaleLowerCase().includes(groupName.toLocaleLowerCase());
  if (!pattern) return nameMatches;
  const regexMatches = pattern.test(modelName);
  return operator === "and"
    ? nameMatches && regexMatches
    : nameMatches || regexMatches;
}
