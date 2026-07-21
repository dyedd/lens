import { type SettingItem } from "@/lib/api";
import {
  DEFAULT_MODEL_TEST_PROMPTS,
  MODEL_TEST_PROMPTS_SETTING_KEY,
  parseModelTestPrompts,
  serializeModelTestPrompts,
} from "@/lib/modelTestPrompts";
import { type UpstreamParamOverrideDraft } from "@/lib/settingsTypes";

import {
  createEmptyUpstreamHeadersDraft,
  parseUpstreamHeadersConfig,
  serializeUpstreamHeadersConfig,
  type UpstreamHeadersDraft,
} from "./upstreamHeaderConfig";
import {
  createEmptyUpstreamParamOverrideDraft,
  parseUpstreamParamOverrideConfig,
  serializeUpstreamParamOverrideConfig,
} from "./upstreamParamOverride";

const PROXY_URL = "proxy_url";
const CORS_ALLOW_ORIGINS = "cors_allow_origins";
const AUTH_ACCESS_TOKEN_MINUTES = "auth_access_token_minutes";
const FIRST_TOKEN_TIMEOUT_SECONDS = "first_token_timeout_seconds";
const STREAM_IDLE_TIMEOUT_SECONDS = "stream_idle_timeout_seconds";
const MAX_REQUEST_BODY_BYTES = "max_request_body_bytes";
const CIRCUIT_BREAKER_THRESHOLD = "circuit_breaker_threshold";
const CIRCUIT_BREAKER_COOLDOWN = "circuit_breaker_cooldown";
const CIRCUIT_BREAKER_MAX_COOLDOWN = "circuit_breaker_max_cooldown";
const HEALTH_WINDOW_SECONDS = "health_window_seconds";
const HEALTH_PENALTY_WEIGHT = "health_penalty_weight";
const HEALTH_MIN_SAMPLES = "health_min_samples";
const RELAY_LOG_BODY_ENABLED = "relay_log_body_enabled";
const MODEL_LIST_COMPAT_MODE_ENABLED = "model_list_compat_mode_enabled";
const UPSTREAM_HEADERS_CONFIG = "upstream_headers_config";
const UPSTREAM_PARAM_OVERRIDE_CONFIG = "upstream_param_override_config";
const SITE_NAME = "site_name";
const SITE_LOGO_URL = "site_logo_url";
const TIME_ZONE = "time_zone";

export const TIME_ZONE_OPTIONS = [
  { value: "Asia/Shanghai", label: "Asia/Shanghai" },
  { value: "UTC", label: "UTC" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "America/New_York", label: "America/New_York" },
] as const;

export interface SettingsDraft {
  proxyUrl: string;
  corsAllowOrigins: string;
  authAccessTokenMinutes: string;
  firstTokenTimeoutSeconds: string;
  streamIdleTimeoutSeconds: string;
  maxRequestBodyBytes: string;
  circuitBreakerThreshold: string;
  circuitBreakerCooldown: string;
  circuitBreakerMaxCooldown: string;
  healthWindowSeconds: string;
  healthPenaltyWeight: string;
  healthMinSamples: string;
  isRelayLogBodyEnabled: boolean;
  isModelListCompatModeEnabled: boolean;
  siteName: string;
  siteLogoUrl: string;
  timeZone: string;
  modelTestPrompts: string;
  upstreamHeadersConfig: UpstreamHeadersDraft;
  upstreamParamOverrideConfig: UpstreamParamOverrideDraft;
}

function _normalizeOriginList(rawValue: string) {
  const items: string[] = [];
  const seen = new Set<string>();
  for (const chunk of rawValue
    .replace(/\r/g, "\n")
    .replaceAll("，", ",")
    .split("\n")) {
    for (const part of chunk.split(",")) {
      const normalized = part.trim();
      if (!normalized || seen.has(normalized)) {
        continue;
      }
      seen.add(normalized);
      items.push(normalized);
    }
  }
  return items.includes("*") ? "*" : items.join(",");
}

/** Create the initial settings form draft. */
export function createEmptySettingsDraft(): SettingsDraft {
  return {
    proxyUrl: "",
    corsAllowOrigins: "*",
    authAccessTokenMinutes: "",
    firstTokenTimeoutSeconds: "180",
    streamIdleTimeoutSeconds: "180",
    maxRequestBodyBytes: "",
    circuitBreakerThreshold: "3",
    circuitBreakerCooldown: "60",
    circuitBreakerMaxCooldown: "600",
    healthWindowSeconds: "300",
    healthPenaltyWeight: "0.5",
    healthMinSamples: "10",
    isRelayLogBodyEnabled: false,
    isModelListCompatModeEnabled: false,
    siteName: "Lens",
    siteLogoUrl: "",
    timeZone: "Asia/Shanghai",
    modelTestPrompts: DEFAULT_MODEL_TEST_PROMPTS.join("\n"),
    upstreamHeadersConfig: createEmptyUpstreamHeadersDraft(),
    upstreamParamOverrideConfig: createEmptyUpstreamParamOverrideDraft(),
  };
}

/** Convert persisted setting items into the editable settings draft. */
export function createSettingsDraft(
  items: SettingItem[] | undefined,
): SettingsDraft {
  const mapping = new Map((items ?? []).map((item) => [item.key, item.value]));
  return {
    proxyUrl: mapping.get(PROXY_URL) ?? "",
    corsAllowOrigins: mapping.get(CORS_ALLOW_ORIGINS) ?? "*",
    authAccessTokenMinutes: mapping.get(AUTH_ACCESS_TOKEN_MINUTES) ?? "",
    firstTokenTimeoutSeconds: mapping.get(FIRST_TOKEN_TIMEOUT_SECONDS) ?? "180",
    streamIdleTimeoutSeconds: mapping.get(STREAM_IDLE_TIMEOUT_SECONDS) ?? "180",
    maxRequestBodyBytes: mapping.get(MAX_REQUEST_BODY_BYTES) ?? "",
    circuitBreakerThreshold: mapping.get(CIRCUIT_BREAKER_THRESHOLD) ?? "3",
    circuitBreakerCooldown: mapping.get(CIRCUIT_BREAKER_COOLDOWN) ?? "60",
    circuitBreakerMaxCooldown:
      mapping.get(CIRCUIT_BREAKER_MAX_COOLDOWN) ?? "600",
    healthWindowSeconds: mapping.get(HEALTH_WINDOW_SECONDS) ?? "300",
    healthPenaltyWeight: mapping.get(HEALTH_PENALTY_WEIGHT) ?? "0.5",
    healthMinSamples: mapping.get(HEALTH_MIN_SAMPLES) ?? "10",
    isRelayLogBodyEnabled:
      (mapping.get(RELAY_LOG_BODY_ENABLED) ?? "false").trim().toLowerCase() ===
      "true",
    isModelListCompatModeEnabled:
      (mapping.get(MODEL_LIST_COMPAT_MODE_ENABLED) ?? "false")
        .trim()
        .toLowerCase() === "true",
    siteName: mapping.get(SITE_NAME) ?? "Lens",
    siteLogoUrl: mapping.get(SITE_LOGO_URL) ?? "",
    timeZone: mapping.get(TIME_ZONE) ?? "Asia/Shanghai",
    modelTestPrompts: parseModelTestPrompts(
      mapping.get(MODEL_TEST_PROMPTS_SETTING_KEY),
    ).join("\n"),
    upstreamHeadersConfig: parseUpstreamHeadersConfig(
      mapping.get(UPSTREAM_HEADERS_CONFIG),
    ),
    upstreamParamOverrideConfig: parseUpstreamParamOverrideConfig(
      mapping.get(UPSTREAM_PARAM_OVERRIDE_CONFIG),
    ),
  };
}

/** Convert an editable settings draft into API setting items. */
export function createSettingItems(draft: SettingsDraft): SettingItem[] {
  return [
    { key: PROXY_URL, value: draft.proxyUrl.trim() },
    {
      key: CORS_ALLOW_ORIGINS,
      value: _normalizeOriginList(draft.corsAllowOrigins) || "*",
    },
    {
      key: AUTH_ACCESS_TOKEN_MINUTES,
      value: draft.authAccessTokenMinutes.trim(),
    },
    {
      key: FIRST_TOKEN_TIMEOUT_SECONDS,
      value: draft.firstTokenTimeoutSeconds.trim(),
    },
    {
      key: STREAM_IDLE_TIMEOUT_SECONDS,
      value: draft.streamIdleTimeoutSeconds.trim(),
    },
    {
      key: MAX_REQUEST_BODY_BYTES,
      value: draft.maxRequestBodyBytes.trim(),
    },
    {
      key: CIRCUIT_BREAKER_THRESHOLD,
      value: draft.circuitBreakerThreshold.trim() || "3",
    },
    {
      key: CIRCUIT_BREAKER_COOLDOWN,
      value: draft.circuitBreakerCooldown.trim() || "60",
    },
    {
      key: CIRCUIT_BREAKER_MAX_COOLDOWN,
      value: draft.circuitBreakerMaxCooldown.trim() || "600",
    },
    {
      key: HEALTH_WINDOW_SECONDS,
      value: draft.healthWindowSeconds.trim() || "300",
    },
    {
      key: HEALTH_PENALTY_WEIGHT,
      value: draft.healthPenaltyWeight.trim() || "0.5",
    },
    {
      key: HEALTH_MIN_SAMPLES,
      value: draft.healthMinSamples.trim() || "10",
    },
    {
      key: RELAY_LOG_BODY_ENABLED,
      value: draft.isRelayLogBodyEnabled ? "true" : "false",
    },
    {
      key: MODEL_LIST_COMPAT_MODE_ENABLED,
      value: draft.isModelListCompatModeEnabled ? "true" : "false",
    },
    { key: SITE_NAME, value: draft.siteName.trim() || "Lens" },
    { key: SITE_LOGO_URL, value: draft.siteLogoUrl.trim() },
    { key: TIME_ZONE, value: draft.timeZone.trim() || "Asia/Shanghai" },
    {
      key: MODEL_TEST_PROMPTS_SETTING_KEY,
      value: serializeModelTestPrompts(draft.modelTestPrompts),
    },
    {
      key: UPSTREAM_HEADERS_CONFIG,
      value: serializeUpstreamHeadersConfig(draft.upstreamHeadersConfig),
    },
    {
      key: UPSTREAM_PARAM_OVERRIDE_CONFIG,
      value: serializeUpstreamParamOverrideConfig(
        draft.upstreamParamOverrideConfig,
      ),
    },
  ];
}
