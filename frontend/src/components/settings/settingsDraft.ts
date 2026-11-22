import type { SettingItem } from "@/lib/api/settings";
import type {
  UpstreamHeadersDraft,
  UpstreamParamOverrideDraft,
} from "@/lib/upstreamRules";

import {
  createEmptyUpstreamHeadersDraft,
  parseUpstreamHeadersConfig,
  serializeUpstreamHeadersConfig,
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
const CIRCUIT_BREAKER_FAILURE_WINDOW = "circuit_breaker_failure_window_seconds";
const CIRCUIT_BREAKER_TIMEOUT_THRESHOLD = "circuit_breaker_timeout_threshold";
const CIRCUIT_BREAKER_NETWORK_THRESHOLD = "circuit_breaker_network_threshold";
const CIRCUIT_BREAKER_COOLDOWN = "circuit_breaker_cooldown";
const CIRCUIT_BREAKER_AUTH_COOLDOWN = "circuit_breaker_auth_cooldown";
const CIRCUIT_BREAKER_NOT_FOUND_COOLDOWN = "circuit_breaker_not_found_cooldown";
const CIRCUIT_BREAKER_RATE_LIMIT_COOLDOWN =
  "circuit_breaker_rate_limit_cooldown";
const CIRCUIT_BREAKER_TIMEOUT_COOLDOWN = "circuit_breaker_timeout_cooldown";
const CIRCUIT_BREAKER_NETWORK_COOLDOWN = "circuit_breaker_network_cooldown";
const CIRCUIT_BREAKER_BACKOFF_MULTIPLIER = "circuit_breaker_backoff_multiplier";
const CIRCUIT_BREAKER_MAX_COOLDOWN = "circuit_breaker_max_cooldown";
const FAILOVER_COOLED_WAIT_SECONDS = "failover_cooled_wait_seconds";
const CIRCUIT_BREAKER_ESCALATE_THRESHOLD = "circuit_breaker_escalate_threshold";
const CIRCUIT_BREAKER_ESCALATE_WINDOW =
  "circuit_breaker_escalate_window_seconds";
const FAILOVER_AFFINITY_SECONDS = "failover_affinity_seconds";
const HEALTH_SCORING_ENABLED = "health_scoring_enabled";
const HEALTH_WINDOW_SECONDS = "health_window_seconds";
const HEALTH_PENALTY_WEIGHT = "health_penalty_weight";
const HEALTH_MIN_SAMPLES = "health_min_samples";
const RELAY_LOG_BODY_ENABLED = "relay_log_body_enabled";
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
  circuitBreakerFailureWindowSeconds: string;
  circuitBreakerTimeoutThreshold: string;
  circuitBreakerNetworkThreshold: string;
  circuitBreakerCooldown: string;
  circuitBreakerAuthCooldown: string;
  circuitBreakerNotFoundCooldown: string;
  circuitBreakerRateLimitCooldown: string;
  circuitBreakerTimeoutCooldown: string;
  circuitBreakerNetworkCooldown: string;
  circuitBreakerBackoffMultiplier: string;
  circuitBreakerMaxCooldown: string;
  failoverCooledWaitSeconds: string;
  circuitBreakerEscalateThreshold: string;
  circuitBreakerEscalateWindowSeconds: string;
  failoverAffinitySeconds: string;
  isHealthScoringEnabled: boolean;
  healthWindowSeconds: string;
  healthPenaltyWeight: string;
  healthMinSamples: string;
  isRelayLogBodyEnabled: boolean;
  siteName: string;
  siteLogoUrl: string;
  timeZone: string;
  upstreamHeadersConfig: UpstreamHeadersDraft;
  upstreamParamOverrideConfig: UpstreamParamOverrideDraft;
}

const SETTINGS_DEFAULTS = {
  proxyUrl: "",
  corsAllowOrigins: "*",
  authAccessTokenMinutes: "",
  firstTokenTimeoutSeconds: "180",
  streamIdleTimeoutSeconds: "180",
  maxRequestBodyBytes: "",
  circuitBreakerThreshold: "3",
  circuitBreakerFailureWindowSeconds: "300",
  circuitBreakerTimeoutThreshold: "2",
  circuitBreakerNetworkThreshold: "2",
  circuitBreakerCooldown: "60",
  circuitBreakerAuthCooldown: "300",
  circuitBreakerNotFoundCooldown: "300",
  circuitBreakerRateLimitCooldown: "60",
  circuitBreakerTimeoutCooldown: "60",
  circuitBreakerNetworkCooldown: "60",
  circuitBreakerBackoffMultiplier: "2",
  circuitBreakerMaxCooldown: "600",
  failoverCooledWaitSeconds: "0",
  circuitBreakerEscalateThreshold: "2",
  circuitBreakerEscalateWindowSeconds: "60",
  failoverAffinitySeconds: "30",
  isHealthScoringEnabled: true,
  healthWindowSeconds: "300",
  healthPenaltyWeight: "0.5",
  healthMinSamples: "10",
  isRelayLogBodyEnabled: false,
  siteName: "Lens",
  siteLogoUrl: "",
  timeZone: "Asia/Shanghai",
} satisfies Omit<
  SettingsDraft,
  "upstreamHeadersConfig" | "upstreamParamOverrideConfig"
>;

function serializeCorsOrigins(rawValue: string) {
  const items: string[] = [];
  const seen = new Set<string>();
  for (const chunk of rawValue
    .replace(/\r/g, "\n")
    .replaceAll("，", ",")
    .split("\n")) {
    for (const part of chunk.split(",")) {
      const trimmedPart = part.trim();
      if (!trimmedPart || seen.has(trimmedPart)) {
        continue;
      }
      seen.add(trimmedPart);
      items.push(trimmedPart);
    }
  }
  return items.includes("*") ? "*" : items.join(",");
}

/** Create the initial settings form draft. */
export function createEmptySettingsDraft(): SettingsDraft {
  return {
    ...SETTINGS_DEFAULTS,
    upstreamHeadersConfig: createEmptyUpstreamHeadersDraft(),
    upstreamParamOverrideConfig: createEmptyUpstreamParamOverrideDraft(),
  };
}

/** Report whether the current draft needs a new automatic save attempt. */
export function shouldAutoSaveSettingsDraft(
  draft: SettingsDraft,
  savedDraft: string | null,
  submittedDraft: string | null,
) {
  if (savedDraft === null) {
    return false;
  }
  const serializedDraft = JSON.stringify(draft);
  return serializedDraft !== savedDraft && serializedDraft !== submittedDraft;
}

/** Convert persisted setting items into the editable settings draft. */
export function createSettingsDraft(
  items: SettingItem[] | undefined,
): SettingsDraft {
  const mapping = new Map((items ?? []).map((item) => [item.key, item.value]));
  const value = (key: string, fallback: string) => mapping.get(key) ?? fallback;
  return {
    proxyUrl: value(PROXY_URL, SETTINGS_DEFAULTS.proxyUrl),
    corsAllowOrigins: value(
      CORS_ALLOW_ORIGINS,
      SETTINGS_DEFAULTS.corsAllowOrigins,
    ),
    authAccessTokenMinutes: value(
      AUTH_ACCESS_TOKEN_MINUTES,
      SETTINGS_DEFAULTS.authAccessTokenMinutes,
    ),
    firstTokenTimeoutSeconds: value(
      FIRST_TOKEN_TIMEOUT_SECONDS,
      SETTINGS_DEFAULTS.firstTokenTimeoutSeconds,
    ),
    streamIdleTimeoutSeconds: value(
      STREAM_IDLE_TIMEOUT_SECONDS,
      SETTINGS_DEFAULTS.streamIdleTimeoutSeconds,
    ),
    maxRequestBodyBytes: value(
      MAX_REQUEST_BODY_BYTES,
      SETTINGS_DEFAULTS.maxRequestBodyBytes,
    ),
    circuitBreakerThreshold: value(
      CIRCUIT_BREAKER_THRESHOLD,
      SETTINGS_DEFAULTS.circuitBreakerThreshold,
    ),
    circuitBreakerFailureWindowSeconds: value(
      CIRCUIT_BREAKER_FAILURE_WINDOW,
      SETTINGS_DEFAULTS.circuitBreakerFailureWindowSeconds,
    ),
    circuitBreakerTimeoutThreshold: value(
      CIRCUIT_BREAKER_TIMEOUT_THRESHOLD,
      SETTINGS_DEFAULTS.circuitBreakerTimeoutThreshold,
    ),
    circuitBreakerNetworkThreshold: value(
      CIRCUIT_BREAKER_NETWORK_THRESHOLD,
      SETTINGS_DEFAULTS.circuitBreakerNetworkThreshold,
    ),
    circuitBreakerCooldown: value(
      CIRCUIT_BREAKER_COOLDOWN,
      SETTINGS_DEFAULTS.circuitBreakerCooldown,
    ),
    circuitBreakerAuthCooldown: value(
      CIRCUIT_BREAKER_AUTH_COOLDOWN,
      SETTINGS_DEFAULTS.circuitBreakerAuthCooldown,
    ),
    circuitBreakerNotFoundCooldown: value(
      CIRCUIT_BREAKER_NOT_FOUND_COOLDOWN,
      SETTINGS_DEFAULTS.circuitBreakerNotFoundCooldown,
    ),
    circuitBreakerRateLimitCooldown: value(
      CIRCUIT_BREAKER_RATE_LIMIT_COOLDOWN,
      SETTINGS_DEFAULTS.circuitBreakerRateLimitCooldown,
    ),
    circuitBreakerTimeoutCooldown: value(
      CIRCUIT_BREAKER_TIMEOUT_COOLDOWN,
      SETTINGS_DEFAULTS.circuitBreakerTimeoutCooldown,
    ),
    circuitBreakerNetworkCooldown: value(
      CIRCUIT_BREAKER_NETWORK_COOLDOWN,
      SETTINGS_DEFAULTS.circuitBreakerNetworkCooldown,
    ),
    circuitBreakerBackoffMultiplier: value(
      CIRCUIT_BREAKER_BACKOFF_MULTIPLIER,
      SETTINGS_DEFAULTS.circuitBreakerBackoffMultiplier,
    ),
    circuitBreakerMaxCooldown: value(
      CIRCUIT_BREAKER_MAX_COOLDOWN,
      SETTINGS_DEFAULTS.circuitBreakerMaxCooldown,
    ),
    failoverCooledWaitSeconds: value(
      FAILOVER_COOLED_WAIT_SECONDS,
      SETTINGS_DEFAULTS.failoverCooledWaitSeconds,
    ),
    circuitBreakerEscalateThreshold: value(
      CIRCUIT_BREAKER_ESCALATE_THRESHOLD,
      SETTINGS_DEFAULTS.circuitBreakerEscalateThreshold,
    ),
    circuitBreakerEscalateWindowSeconds: value(
      CIRCUIT_BREAKER_ESCALATE_WINDOW,
      SETTINGS_DEFAULTS.circuitBreakerEscalateWindowSeconds,
    ),
    failoverAffinitySeconds: value(
      FAILOVER_AFFINITY_SECONDS,
      SETTINGS_DEFAULTS.failoverAffinitySeconds,
    ),
    isHealthScoringEnabled:
      value(
        HEALTH_SCORING_ENABLED,
        String(SETTINGS_DEFAULTS.isHealthScoringEnabled),
      )
        .trim()
        .toLowerCase() === "true",
    healthWindowSeconds: value(
      HEALTH_WINDOW_SECONDS,
      SETTINGS_DEFAULTS.healthWindowSeconds,
    ),
    healthPenaltyWeight: value(
      HEALTH_PENALTY_WEIGHT,
      SETTINGS_DEFAULTS.healthPenaltyWeight,
    ),
    healthMinSamples: value(
      HEALTH_MIN_SAMPLES,
      SETTINGS_DEFAULTS.healthMinSamples,
    ),
    isRelayLogBodyEnabled:
      value(
        RELAY_LOG_BODY_ENABLED,
        String(SETTINGS_DEFAULTS.isRelayLogBodyEnabled),
      )
        .trim()
        .toLowerCase() === "true",
    siteName: value(SITE_NAME, SETTINGS_DEFAULTS.siteName),
    siteLogoUrl: value(SITE_LOGO_URL, SETTINGS_DEFAULTS.siteLogoUrl),
    timeZone: value(TIME_ZONE, SETTINGS_DEFAULTS.timeZone),
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
      value: serializeCorsOrigins(draft.corsAllowOrigins) || "*",
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
      value:
        draft.circuitBreakerThreshold.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerThreshold,
    },
    {
      key: CIRCUIT_BREAKER_FAILURE_WINDOW,
      value:
        draft.circuitBreakerFailureWindowSeconds.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerFailureWindowSeconds,
    },
    {
      key: CIRCUIT_BREAKER_TIMEOUT_THRESHOLD,
      value:
        draft.circuitBreakerTimeoutThreshold.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerTimeoutThreshold,
    },
    {
      key: CIRCUIT_BREAKER_NETWORK_THRESHOLD,
      value:
        draft.circuitBreakerNetworkThreshold.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerNetworkThreshold,
    },
    {
      key: CIRCUIT_BREAKER_COOLDOWN,
      value:
        draft.circuitBreakerCooldown.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerCooldown,
    },
    {
      key: CIRCUIT_BREAKER_AUTH_COOLDOWN,
      value:
        draft.circuitBreakerAuthCooldown.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerAuthCooldown,
    },
    {
      key: CIRCUIT_BREAKER_NOT_FOUND_COOLDOWN,
      value:
        draft.circuitBreakerNotFoundCooldown.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerNotFoundCooldown,
    },
    {
      key: CIRCUIT_BREAKER_RATE_LIMIT_COOLDOWN,
      value:
        draft.circuitBreakerRateLimitCooldown.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerRateLimitCooldown,
    },
    {
      key: CIRCUIT_BREAKER_TIMEOUT_COOLDOWN,
      value:
        draft.circuitBreakerTimeoutCooldown.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerTimeoutCooldown,
    },
    {
      key: CIRCUIT_BREAKER_NETWORK_COOLDOWN,
      value:
        draft.circuitBreakerNetworkCooldown.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerNetworkCooldown,
    },
    {
      key: CIRCUIT_BREAKER_BACKOFF_MULTIPLIER,
      value:
        draft.circuitBreakerBackoffMultiplier.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerBackoffMultiplier,
    },
    {
      key: CIRCUIT_BREAKER_MAX_COOLDOWN,
      value:
        draft.circuitBreakerMaxCooldown.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerMaxCooldown,
    },
    {
      key: FAILOVER_COOLED_WAIT_SECONDS,
      value:
        draft.failoverCooledWaitSeconds.trim() ||
        SETTINGS_DEFAULTS.failoverCooledWaitSeconds,
    },
    {
      key: CIRCUIT_BREAKER_ESCALATE_THRESHOLD,
      value:
        draft.circuitBreakerEscalateThreshold.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerEscalateThreshold,
    },
    {
      key: CIRCUIT_BREAKER_ESCALATE_WINDOW,
      value:
        draft.circuitBreakerEscalateWindowSeconds.trim() ||
        SETTINGS_DEFAULTS.circuitBreakerEscalateWindowSeconds,
    },
    {
      key: FAILOVER_AFFINITY_SECONDS,
      value:
        draft.failoverAffinitySeconds.trim() ||
        SETTINGS_DEFAULTS.failoverAffinitySeconds,
    },
    {
      key: HEALTH_SCORING_ENABLED,
      value: draft.isHealthScoringEnabled ? "true" : "false",
    },
    {
      key: HEALTH_WINDOW_SECONDS,
      value:
        draft.healthWindowSeconds.trim() ||
        SETTINGS_DEFAULTS.healthWindowSeconds,
    },
    {
      key: HEALTH_PENALTY_WEIGHT,
      value:
        draft.healthPenaltyWeight.trim() ||
        SETTINGS_DEFAULTS.healthPenaltyWeight,
    },
    {
      key: HEALTH_MIN_SAMPLES,
      value:
        draft.healthMinSamples.trim() || SETTINGS_DEFAULTS.healthMinSamples,
    },
    {
      key: RELAY_LOG_BODY_ENABLED,
      value: draft.isRelayLogBodyEnabled ? "true" : "false",
    },
    {
      key: SITE_NAME,
      value: draft.siteName.trim() || SETTINGS_DEFAULTS.siteName,
    },
    { key: SITE_LOGO_URL, value: draft.siteLogoUrl.trim() },
    {
      key: TIME_ZONE,
      value: draft.timeZone.trim() || SETTINGS_DEFAULTS.timeZone,
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
