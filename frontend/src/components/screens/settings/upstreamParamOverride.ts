import { type Locale, titleForLocale } from "@/lib/I18nContext";
import {
  EMPTY_PARAM_OVERRIDE_RULE,
  type ParamOverrideRule,
  paramOverrideDraftToRules,
  paramOverrideRulesToDraft,
  type UpstreamParamOverrideDraft,
} from "@/lib/upstreamRules";

import { parseJsonObject } from "./upstreamConfigUtils";

export type { ParamOverrideRule, UpstreamParamOverrideDraft };

export function createEmptyUpstreamParamOverrideDraft(): UpstreamParamOverrideDraft {
  return { rules: [{ ...EMPTY_PARAM_OVERRIDE_RULE }] };
}

export function parseUpstreamParamOverrideConfig(
  rawValue: string | undefined,
): UpstreamParamOverrideDraft {
  const payload = rawValue?.trim() ? parseJsonObject(rawValue) : null;
  return {
    rules: Array.isArray(payload?.rules)
      ? paramOverrideRulesToDraft(
          payload.rules.filter(
            (rule): rule is ParamOverrideRule =>
              Boolean(rule) && typeof rule === "object",
          ),
        )
      : [{ ...EMPTY_PARAM_OVERRIDE_RULE }],
  };
}

export function serializeUpstreamParamOverrideConfig(
  config: UpstreamParamOverrideDraft,
) {
  return JSON.stringify({ rules: paramOverrideDraftToRules(config.rules) });
}

export function validateUpstreamParamOverrideConfig(
  config: UpstreamParamOverrideDraft,
  locale: Locale,
) {
  for (const rule of config.rules) {
    const path = rule.path.trim();
    if (!path) continue;
    if (path === "model" || path.startsWith("model.")) {
      return titleForLocale(
        locale,
        "参数规则不可覆盖 model。",
        "Parameter rules cannot override model.",
      );
    }
    if (rule.action === "set" && !rule.value.trim()) {
      return titleForLocale(
        locale,
        "参数值不能为空。",
        "Parameter values are required.",
      );
    }
  }
  return null;
}
