import { titleForLocale, type Locale } from "@/lib/I18nContext";

import type { SettingsDraft } from "./settingsDraft";

export type NumericSettingKey =
  | "authAccessTokenMinutes"
  | "firstTokenTimeoutSeconds"
  | "streamIdleTimeoutSeconds"
  | "maxRequestBodyBytes"
  | "circuitBreakerThreshold"
  | "circuitBreakerFailureWindowSeconds"
  | "circuitBreakerTimeoutThreshold"
  | "circuitBreakerNetworkThreshold"
  | "circuitBreakerCooldown"
  | "circuitBreakerAuthCooldown"
  | "circuitBreakerNotFoundCooldown"
  | "circuitBreakerRateLimitCooldown"
  | "circuitBreakerTimeoutCooldown"
  | "circuitBreakerNetworkCooldown"
  | "circuitBreakerBackoffMultiplier"
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
    labelZh: "5xx 失败阈值",
    labelEn: "5xx failure threshold",
    type: "integer",
    min: 1,
  },
  {
    key: "circuitBreakerFailureWindowSeconds",
    labelZh: "连续失败窗口",
    labelEn: "Consecutive-failure window",
    type: "integer",
    min: 1,
    max: 604_800,
  },
  {
    key: "circuitBreakerTimeoutThreshold",
    labelZh: "超时失败阈值",
    labelEn: "Timeout failure threshold",
    type: "integer",
    min: 1,
  },
  {
    key: "circuitBreakerNetworkThreshold",
    labelZh: "网络失败阈值",
    labelEn: "Network failure threshold",
    type: "integer",
    min: 1,
  },
  {
    key: "circuitBreakerCooldown",
    labelZh: "5xx 初始冷却",
    labelEn: "5xx initial cooldown",
    type: "integer",
    min: 0,
    max: 604_800,
  },
  {
    key: "circuitBreakerAuthCooldown",
    labelZh: "认证错误初始冷却",
    labelEn: "Authentication initial cooldown",
    type: "integer",
    min: 0,
    max: 604_800,
  },
  {
    key: "circuitBreakerNotFoundCooldown",
    labelZh: "404 初始冷却",
    labelEn: "404 initial cooldown",
    type: "integer",
    min: 0,
    max: 604_800,
  },
  {
    key: "circuitBreakerRateLimitCooldown",
    labelZh: "限流初始冷却",
    labelEn: "Rate-limit initial cooldown",
    type: "integer",
    min: 0,
    max: 604_800,
  },
  {
    key: "circuitBreakerTimeoutCooldown",
    labelZh: "超时初始冷却",
    labelEn: "Timeout initial cooldown",
    type: "integer",
    min: 0,
    max: 604_800,
  },
  {
    key: "circuitBreakerNetworkCooldown",
    labelZh: "网络错误初始冷却",
    labelEn: "Network initial cooldown",
    type: "integer",
    min: 0,
    max: 604_800,
  },
  {
    key: "circuitBreakerBackoffMultiplier",
    labelZh: "冷却退避倍率",
    labelEn: "Cooldown backoff multiplier",
    type: "number",
    min: 1,
    max: 10,
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
    max: 604_800,
  },
  {
    key: "healthPenaltyWeight",
    labelZh: "健康惩罚权重",
    labelEn: "Health penalty weight",
    type: "number",
    min: 0,
    max: 1,
  },
  {
    key: "healthMinSamples",
    labelZh: "完整置信样本数",
    labelEn: "Full-confidence sample count",
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
