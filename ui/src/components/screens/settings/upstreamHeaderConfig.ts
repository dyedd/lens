import { titleForLocale, type Locale } from "@/lib/I18nContext";

import {
  createDraftId,
  isRecord,
  parseJsonObject,
  parseModelListText,
} from "./upstreamConfigUtils";

export type HeaderItem = { key: string; value: string };
export type UpstreamHeaderMatchType = "exact" | "regex";

export interface UpstreamHeaderRuleDraft {
  id: string;
  enabled: boolean;
  name: string;
  matchType: UpstreamHeaderMatchType;
  models: string;
  pattern: string;
  headers: HeaderItem[];
}

export interface UpstreamHeadersDraft {
  global: HeaderItem[];
  rules: UpstreamHeaderRuleDraft[];
}

const EMPTY_HEADERS: HeaderItem[] = [{ key: "", value: "" }];

function _parseHeaderRows(value: unknown): HeaderItem[] {
  if (!isRecord(value)) {
    return [{ key: "", value: "" }];
  }
  const rows = Object.entries(value)
    .map(([key, rawValue]) => ({
      key,
      value: typeof rawValue === "string" ? rawValue : String(rawValue ?? ""),
    }))
    .filter((item) => item.key.trim());
  return rows.length ? rows : [{ key: "", value: "" }];
}

function _headersToRecord(headers: HeaderItem[]) {
  const output: Record<string, string> = {};
  const lowerToKey = new Map<string, string>();
  for (const item of headers) {
    const key = item.key.trim();
    if (!key) {
      continue;
    }
    const lowerKey = key.toLowerCase();
    const existingKey = lowerToKey.get(lowerKey);
    if (existingKey) {
      delete output[existingKey];
    }
    lowerToKey.set(lowerKey, key);
    output[key] = item.value.trim();
  }
  return output;
}

function _hasHeaderDraftContent(headers: HeaderItem[]) {
  return headers.some((header) => header.key.trim() || header.value.trim());
}

function _hasHeaderValueWithoutKey(headers: HeaderItem[]) {
  return headers.some((header) => header.value.trim() && !header.key.trim());
}

function _hasRuleDraftContent(rule: UpstreamHeaderRuleDraft) {
  return Boolean(
    rule.name.trim() ||
    rule.models.trim() ||
    rule.pattern.trim() ||
    _hasHeaderDraftContent(rule.headers),
  );
}

/** Create an empty upstream header configuration draft. */
export function createEmptyUpstreamHeadersDraft(): UpstreamHeadersDraft {
  return { global: [...EMPTY_HEADERS], rules: [] };
}

/** Create an empty model-specific upstream header rule. */
export function createEmptyUpstreamHeaderRule(): UpstreamHeaderRuleDraft {
  return {
    id: createDraftId("upstream-header-rule"),
    enabled: true,
    name: "",
    matchType: "exact",
    models: "",
    pattern: "",
    headers: [{ key: "", value: "" }],
  };
}

/** Parse persisted upstream header settings into an editable draft. */
export function parseUpstreamHeadersConfig(
  rawValue: string | undefined,
): UpstreamHeadersDraft {
  if (!rawValue?.trim()) {
    return createEmptyUpstreamHeadersDraft();
  }
  const payload = parseJsonObject(rawValue);
  if (!payload) {
    return createEmptyUpstreamHeadersDraft();
  }
  const rawRules = Array.isArray(payload["rules"]) ? payload["rules"] : [];
  return {
    global: _parseHeaderRows(payload["global"]),
    rules: rawRules.filter(isRecord).map((rule) => {
      const matchType = rule["match_type"] === "regex" ? "regex" : "exact";
      const rawModels = Array.isArray(rule["models"]) ? rule["models"] : [];
      const models = rawModels
        .map((item) => String(item ?? "").trim())
        .filter(Boolean)
        .join("\n");
      return {
        id: createDraftId("upstream-header-rule"),
        enabled: rule["enabled"] !== false,
        name: typeof rule["name"] === "string" ? rule["name"] : "",
        matchType,
        models,
        pattern: typeof rule["pattern"] === "string" ? rule["pattern"] : "",
        headers: _parseHeaderRows(rule["headers"]),
      };
    }),
  };
}

/** Serialize an upstream header draft for persistence. */
export function serializeUpstreamHeadersConfig(config: UpstreamHeadersDraft) {
  const rules = config.rules.flatMap((rule) => {
    if (!_hasRuleDraftContent(rule)) {
      return [];
    }
    const headers = _headersToRecord(rule.headers);
    if (!Object.keys(headers).length) {
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
        headers,
      },
    ];
  });
  return JSON.stringify({
    global: _headersToRecord(config.global),
    rules,
  });
}

/** Validate an upstream header draft and return a localized error. */
export function validateUpstreamHeadersConfig(
  config: UpstreamHeadersDraft,
  locale: Locale,
) {
  if (_hasHeaderValueWithoutKey(config.global)) {
    return titleForLocale(
      locale,
      "全局请求头名称不能为空。",
      "Global header keys are required.",
    );
  }
  for (const rule of config.rules) {
    if (!_hasRuleDraftContent(rule)) {
      continue;
    }
    if (_hasHeaderValueWithoutKey(rule.headers)) {
      return titleForLocale(
        locale,
        "规则请求头名称不能为空。",
        "Rule header keys are required.",
      );
    }
    if (!Object.keys(_headersToRecord(rule.headers)).length) {
      return titleForLocale(
        locale,
        "模型请求头规则需要至少填写一个请求头名称。",
        "Model header rules need at least one header key.",
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
