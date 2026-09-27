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

/** Format how many channels and groups use a rule. */
export function formatRegexRuleUsage(rule: RegexRule, locale: Locale) {
  return titleForLocale(
    locale,
    `${rule.sites.length} 渠道 · ${rule.groups.length} 模型组`,
    `${rule.sites.length} channels · ${rule.groups.length} groups`,
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

/** List the channels and groups that use a rule, one line per kind. */
export function listRegexRuleUsageLines(rule: RegexRule, locale: Locale) {
  return [
    rule.sites.length
      ? `${titleForLocale(locale, "渠道：", "Channels: ")}${formatReferenceNames(rule.sites, locale)}`
      : "",
    rule.groups.length
      ? `${titleForLocale(locale, "模型组：", "Groups: ")}${formatReferenceNames(rule.groups, locale)}`
      : "",
  ].filter(Boolean);
}
