import { titleForLocale, type Locale } from "@/lib/I18nContext";
import {
  type UpstreamParamOverrideDraft,
  type UpstreamParamOverrideRuleDraft,
} from "@/lib/settingsTypes";

import {
  createDraftId,
  formatJsonObject,
  isRecord,
  parseJsonObject,
  parseModelListText,
} from "./upstreamConfigUtils";

function _hasParamRuleContent(rule: UpstreamParamOverrideRuleDraft) {
  return Boolean(
    rule.name.trim() ||
    rule.models.trim() ||
    rule.pattern.trim() ||
    rule.override.trim(),
  );
}

/** Create an empty upstream parameter override configuration. */
export function createEmptyUpstreamParamOverrideDraft(): UpstreamParamOverrideDraft {
  return { global: "{}", rules: [] };
}

/** Create an empty model-specific parameter override rule. */
export function createEmptyUpstreamParamOverrideRule(): UpstreamParamOverrideRuleDraft {
  return {
    id: createDraftId("upstream-param-override-rule"),
    enabled: true,
    name: "",
    matchType: "exact",
    models: "",
    pattern: "",
    override: "",
  };
}

/** Parse persisted parameter overrides into an editable draft. */
export function parseUpstreamParamOverrideConfig(
  rawValue: string | undefined,
): UpstreamParamOverrideDraft {
  if (!rawValue?.trim()) {
    return createEmptyUpstreamParamOverrideDraft();
  }
  const payload = parseJsonObject(rawValue);
  if (!payload) {
    return createEmptyUpstreamParamOverrideDraft();
  }
  const rawRules = Array.isArray(payload["rules"]) ? payload["rules"] : [];
  return {
    global: formatJsonObject(payload["global"]) || "{}",
    rules: rawRules.filter(isRecord).map((rule) => {
      const matchType = rule["match_type"] === "regex" ? "regex" : "exact";
      const rawModels = Array.isArray(rule["models"]) ? rule["models"] : [];
      const models = rawModels
        .map((item) => String(item ?? "").trim())
        .filter(Boolean)
        .join("\n");
      return {
        id: createDraftId("upstream-param-override-rule"),
        enabled: rule["enabled"] !== false,
        name: typeof rule["name"] === "string" ? rule["name"] : "",
        matchType,
        models,
        pattern: typeof rule["pattern"] === "string" ? rule["pattern"] : "",
        override: formatJsonObject(rule["override"]),
      };
    }),
  };
}

/** Serialize a parameter override draft for persistence. */
export function serializeUpstreamParamOverrideConfig(
  config: UpstreamParamOverrideDraft,
) {
  const rules = config.rules.flatMap((rule) => {
    const override = parseJsonObject(rule.override);
    if (override === null || Object.keys(override).length === 0) {
      return [];
    }
    const models = parseModelListText(rule.models);
    const pattern = rule.pattern.trim();
    if (rule.matchType === "exact" && !models.length) {
      return [];
    }
    if (rule.matchType === "regex" && !pattern) {
      return [];
    }
    return [
      {
        enabled: rule.enabled,
        name: rule.name.trim(),
        match_type: rule.matchType,
        models,
        pattern,
        override,
      },
    ];
  });
  const globalOverride = parseJsonObject(config.global);
  return JSON.stringify({ global: globalOverride, rules });
}

/** Validate a parameter override draft and return a localized error. */
export function validateUpstreamParamOverrideConfig(
  config: UpstreamParamOverrideDraft,
  locale: Locale,
) {
  const globalOverride = parseJsonObject(config.global);
  if (globalOverride === null) {
    return titleForLocale(
      locale,
      "全局参数不是合法的 JSON 对象。",
      "Global params must be a valid JSON object.",
    );
  }
  if ("model" in globalOverride) {
    return titleForLocale(
      locale,
      "全局参数不可包含 model。",
      "Global params cannot include model.",
    );
  }
  for (const rule of config.rules) {
    if (!_hasParamRuleContent(rule)) {
      continue;
    }
    const override = parseJsonObject(rule.override);
    if (override === null) {
      return titleForLocale(
        locale,
        "覆盖参数不是合法的 JSON 对象。",
        "Override params must be a valid JSON object.",
      );
    }
    if ("model" in override) {
      return titleForLocale(
        locale,
        "覆盖参数不可包含 model。",
        "Override params cannot include model.",
      );
    }
    if (Object.keys(override).length === 0) {
      return titleForLocale(
        locale,
        "参数覆盖规则需要至少填写一个覆盖参数。",
        "Param override rules need at least one override param.",
      );
    }
    if (rule.matchType === "exact" && !parseModelListText(rule.models).length) {
      return titleForLocale(
        locale,
        "精确匹配规则需要填写至少一个模型名称。",
        "Exact match rules need at least one model name.",
      );
    }
    if (rule.matchType === "regex" && !rule.pattern.trim()) {
      return titleForLocale(
        locale,
        "正则匹配规则需要填写模型正则。",
        "Regex match rules need a model regex.",
      );
    }
  }
  return null;
}
