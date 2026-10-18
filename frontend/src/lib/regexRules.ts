import type { RegexRule, RegexRuleReference } from "@/lib/api/regexRules";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

const USAGE_NAME_PREVIEW_LIMIT = 5;

/** Compile a rule pattern case-insensitively, or null when empty or invalid. */
export function compileRegexRulePattern(pattern: string) {
  const trimmedPattern = pattern.trim();
  // Python accepts a leading (?i); JS takes the flag instead.
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

/** Format how many groups and channels use a rule. */
export function formatRegexRuleUsage(rule: RegexRule, locale: Locale) {
  return titleForLocale(
    locale,
    `${rule.groups.length} 个模型组 · ${rule.sites.length} 个渠道`,
    `${rule.groups.length} groups · ${rule.sites.length} channels`,
  );
}

function formatReferenceNames(
  references: RegexRuleReference[],
  locale: Locale,
) {
  const names = references
    .slice(0, USAGE_NAME_PREVIEW_LIMIT)
    .map((reference) => reference.name)
    .join(titleForLocale(locale, "、", ", "));
  return references.length > USAGE_NAME_PREVIEW_LIMIT
    ? `${names}${titleForLocale(locale, " 等", ", …")}`
    : names;
}

/** List the groups and channels that use a rule. */
export function listRegexRuleUsageLines(rule: RegexRule, locale: Locale) {
  return [
    rule.groups.length
      ? `${titleForLocale(locale, "模型组：", "Groups: ")}${formatReferenceNames(rule.groups, locale)}`
      : "",
    rule.sites.length
      ? `${titleForLocale(locale, "渠道：", "Channels: ")}${formatReferenceNames(rule.sites, locale)}`
      : "",
  ].filter(Boolean);
}
