import { type Locale, titleForLocale } from "@/lib/I18nContext";
import type { UpstreamParamOverrideDraft } from "@/lib/settingsTypes";

import { formatJsonObject, parseJsonObject } from "./upstreamConfigUtils";

/** Create an empty upstream parameter override configuration. */
export function createEmptyUpstreamParamOverrideDraft(): UpstreamParamOverrideDraft {
  return { global: "{}" };
}

/** Parse persisted parameter overrides into an editable draft. */
export function parseUpstreamParamOverrideConfig(
  rawValue: string | undefined,
): UpstreamParamOverrideDraft {
  const payload = rawValue?.trim() ? parseJsonObject(rawValue) : null;
  return {
    global: formatJsonObject(payload?.global) || "{}",
  };
}

/** Serialize a parameter override draft for persistence. */
export function serializeUpstreamParamOverrideConfig(
  config: UpstreamParamOverrideDraft,
) {
  const globalOverride = parseJsonObject(config.global);
  return JSON.stringify({ global: globalOverride ?? {} });
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
  return null;
}
