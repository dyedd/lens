import { titleForLocale, type Locale } from "@/lib/I18nContext";

import type { SettingsDraft } from "./settingsDraft";

export type NumericSettingKey =
  | "authAccessTokenMinutes"
  | "firstTokenTimeoutSeconds"
  | "streamIdleTimeoutSeconds"
  | "maxRequestBodyBytes"
  | "circuitBreakerThreshold"
  | "circuitBreakerCooldown"
  | "circuitBreakerMaxCooldown"
  | "healthWindowSeconds"
  | "healthPenaltyWeight"
  | "healthMinSamples";

export type NumericSettingErrors = Partial<Record<NumericSettingKey, string>>;

const INTEGER_PATTERN = /^-?\d+$/;
const FINITE_NUMBER_PATTERN = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;

const NUMERIC_SETTING_RULES: ReadonlyArray<{
  key: NumericSettingKey;
  labelZh: string;
  labelEn: string;
  type: "integer" | "number";
  min: 0 | 1;
  max?: number;
}> = [
  {
    key: "authAccessTokenMinutes",
    labelZh: "访问令牌有效期",
    labelEn: "Access token lifetime",
    type: "integer",
    min: 1,
    max: 525_600,
  },
  {
    key: "firstTokenTimeoutSeconds",
    labelZh: "首字超时",
    labelEn: "First-token timeout",
    type: "number",
    min: 0,
    max: 86_400,
  },
  {
    key: "streamIdleTimeoutSeconds",
    labelZh: "流空闲超时",
    labelEn: "Stream idle timeout",
    type: "number",
    min: 0,
    max: 86_400,
  },
  {
    key: "maxRequestBodyBytes",
    labelZh: "最大请求体",
    labelEn: "Maximum request body",
    type: "integer",
    min: 0,
  },
  {
    key: "circuitBreakerThreshold",
    labelZh: "失败阈值",
    labelEn: "Failure threshold",
    type: "integer",
    min: 1,
  },
  {
    key: "circuitBreakerCooldown",
    labelZh: "基础冷却秒数",
    labelEn: "Cooldown seconds",
    type: "integer",
    min: 0,
    max: 604_800,
  },
  {
    key: "circuitBreakerMaxCooldown",
    labelZh: "最大冷却秒数",
    labelEn: "Max cooldown seconds",
    type: "integer",
    min: 0,
    max: 604_800,
  },
  {
    key: "healthWindowSeconds",
    labelZh: "健康窗口秒数",
    labelEn: "Health window seconds",
    type: "integer",
    min: 1,
  },
  {
    key: "healthPenaltyWeight",
    labelZh: "健康惩罚权重",
    labelEn: "Health penalty weight",
    type: "number",
    min: 0,
  },
  {
    key: "healthMinSamples",
    labelZh: "健康最小样本数",
    labelEn: "Health min samples",
    type: "integer",
    min: 1,
  },
];

/** Validate all numeric settings before saving. */
export function validateNumericSettings(
  draft: SettingsDraft,
  locale: Locale,
): NumericSettingErrors {
  const errors: NumericSettingErrors = {};
  for (const rule of NUMERIC_SETTING_RULES) {
    const rawValue = draft[rule.key].trim();
    if (!rawValue) {
      errors[rule.key] = titleForLocale(
        locale,
        `${rule.labelZh}不能为空。`,
        `${rule.labelEn} is required.`,
      );
      continue;
    }

    const value = Number(rawValue);
    const isValidType =
      rule.type === "integer"
        ? INTEGER_PATTERN.test(rawValue) && Number.isFinite(value)
        : FINITE_NUMBER_PATTERN.test(rawValue) && Number.isFinite(value);
    if (!isValidType) {
      errors[rule.key] = titleForLocale(
        locale,
        rule.type === "integer"
          ? `${rule.labelZh}必须是整数。`
          : `${rule.labelZh}必须是有限数字。`,
        rule.type === "integer"
          ? `${rule.labelEn} must be an integer.`
          : `${rule.labelEn} must be a finite number.`,
      );
      continue;
    }

    const isBelowMinimum =
      value < rule.min ||
      (rule.type === "integer" && rule.min === 0 && rawValue.startsWith("-"));
    if (isBelowMinimum || (rule.max !== undefined && value > rule.max)) {
      errors[rule.key] = titleForLocale(
        locale,
        rule.max !== undefined
          ? `${rule.labelZh}必须在 ${rule.min} 到 ${rule.max} 之间。`
          : rule.min === 1
            ? `${rule.labelZh}必须大于 0。`
            : `${rule.labelZh}不能为负数。`,
        rule.max !== undefined
          ? `${rule.labelEn} must be between ${rule.min} and ${rule.max}.`
          : rule.min === 1
            ? `${rule.labelEn} must be greater than 0.`
            : `${rule.labelEn} must not be negative.`,
      );
    }
  }
  return errors;
}
