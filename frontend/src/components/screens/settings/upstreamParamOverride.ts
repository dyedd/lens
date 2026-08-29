import { type Locale, titleForLocale } from "@/lib/I18nContext";

import type {
  ParamOverrideRule,
  UpstreamParamOverrideDraft,
} from "@/lib/settingsTypes";
import { formatJsonObject, parseJsonObject } from "./upstreamConfigUtils";

export type { ParamOverrideRule };

export function createEmptyUpstreamParamOverrideDraft(): UpstreamParamOverrideDraft {
  return { rules: [{ path: "", action: "set", value: "" }] };
}

export function parseUpstreamParamOverrideConfig(
  rawValue: string | undefined,
): UpstreamParamOverrideDraft {
  const payload = rawValue?.trim() ? parseJsonObject(rawValue) : null;
  const rules = Array.isArray(payload?.rules)
    ? payload.rules
        .filter(
          (rule): rule is Record<string, unknown> =>
            Boolean(rule) && typeof rule === "object",
        )
        .map((rule) => ({
          path: typeof rule.path === "string" ? rule.path : "",
          action:
            rule.action === "delete" ? ("delete" as const) : ("set" as const),
          value: rule.value === undefined ? "" : JSON.stringify(rule.value),
        }))
    : [];
  return {
    rules: rules.length ? rules : [{ path: "", action: "set", value: "" }],
  };
}

export function serializeUpstreamParamOverrideConfig(
  config: UpstreamParamOverrideDraft,
) {
  return JSON.stringify({
    rules: config.rules
      .filter((rule) => rule.path.trim())
      .map((rule) => ({
        path: rule.path.trim(),
        action: rule.action,
        ...(rule.action === "set"
          ? { value: parseJsonObject(rule.value) ?? rule.value }
          : {}),
      })),
  });
}

export function validateUpstreamParamOverrideConfig(
  config: UpstreamParamOverrideDraft,
  locale: Locale,
) {
  for (const rule of config.rules) {
    if (!rule.path.trim()) continue;
    if (rule.path.trim() === "model" || rule.path.trim().startsWith("model.")) {
      return titleForLocale(
        locale,
        "参数规则不可覆盖 model。",
        "Parameter rules cannot override model.",
      );
    }
    if (
      rule.action === "set" &&
      parseJsonObject(rule.value) === null &&
      !rule.value.trim()
    ) {
      return titleForLocale(
        locale,
        "参数值不能为空。",
        "Parameter values are required.",
      );
    }
  }
  return null;
}
