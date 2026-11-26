import { ApiError, apiRequest, isRecord } from "./client";

export type PrivacyAction = "mask" | "warn" | "block";
export type PrivacyCategory = "secrets" | "personal" | "custom";
export type PrivacyConfig = {
  enabled: boolean;
  categories: ("secrets" | "personal")[];
  action: PrivacyAction;
  words: string[];
  regex_rules: { pattern: string }[];
  exceptions: string[];
};
export type PrivacyHit = {
  category: PrivacyCategory;
  action: PrivacyAction;
  count: number;
  placeholders: string[];
};
export type PrivacyPreview = {
  text: string;
  hits: PrivacyHit[];
  blocked: boolean;
};

export function defaultPrivacyConfig(): PrivacyConfig {
  return {
    enabled: false,
    categories: ["secrets", "personal"],
    action: "mask",
    words: [],
    regex_rules: [],
    exceptions: [],
  };
}

function isStrings(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((entry) => typeof entry === "string")
  );
}

export function isPrivacyAction(value: unknown): value is PrivacyAction {
  return value === "mask" || value === "warn" || value === "block";
}

export function isPrivacyHit(value: unknown): value is PrivacyHit {
  return (
    isRecord(value) &&
    (value.category === "secrets" ||
      value.category === "personal" ||
      value.category === "custom") &&
    isPrivacyAction(value.action) &&
    Number.isInteger(value.count) &&
    typeof value.count === "number" &&
    value.count > 0 &&
    isStrings(value.placeholders)
  );
}

export function parsePrivacyConfig(raw: string | undefined): PrivacyConfig {
  if (!raw) return defaultPrivacyConfig();
  const value: unknown = JSON.parse(raw);
  if (
    !isRecord(value) ||
    typeof value.enabled !== "boolean" ||
    !isPrivacyAction(value.action) ||
    !Array.isArray(value.categories) ||
    !value.categories.every(
      (category) => category === "secrets" || category === "personal",
    ) ||
    !isStrings(value.words) ||
    !isStrings(value.exceptions) ||
    !Array.isArray(value.regex_rules) ||
    !value.regex_rules.every(
      (rule): rule is { pattern: string } =>
        isRecord(rule) && typeof rule.pattern === "string",
    )
  ) {
    throw new Error("Invalid privacy settings");
  }
  return {
    enabled: value.enabled,
    action: value.action,
    categories: value.categories,
    words: value.words,
    exceptions: value.exceptions,
    regex_rules: value.regex_rules,
  };
}

export async function previewPrivacy(
  text: string,
  config: PrivacyConfig,
): Promise<PrivacyPreview> {
  const result = await apiRequest<unknown>("/admin/settings/privacy/preview", {
    method: "POST",
    body: JSON.stringify({ text, config }),
  });
  if (
    !isRecord(result) ||
    typeof result.text !== "string" ||
    typeof result.blocked !== "boolean" ||
    !Array.isArray(result.hits) ||
    !result.hits.every(isPrivacyHit)
  ) {
    throw new ApiError("Invalid privacy preview response", 200);
  }
  return { text: result.text, blocked: result.blocked, hits: result.hits };
}
