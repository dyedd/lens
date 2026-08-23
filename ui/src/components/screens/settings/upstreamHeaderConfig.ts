import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { isRecord, parseJsonObject } from "./upstreamConfigUtils";

export type HeaderItem = { key: string; value: string };
export interface UpstreamHeadersDraft {
  global: HeaderItem[];
}

const EMPTY_HEADERS: HeaderItem[] = [{ key: "", value: "" }];

export function parseHeaderRows(value: unknown): HeaderItem[] {
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

export function headersToRecord(headers: HeaderItem[]) {
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

function _hasHeaderValueWithoutKey(headers: HeaderItem[]) {
  return headers.some((header) => header.value.trim() && !header.key.trim());
}

/** Create an empty upstream header configuration draft. */
export function createEmptyUpstreamHeadersDraft(): UpstreamHeadersDraft {
  return { global: [...EMPTY_HEADERS] };
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
  return {
    global: parseHeaderRows(payload["global"]),
  };
}

/** Serialize an upstream header draft for persistence. */
export function serializeUpstreamHeadersConfig(config: UpstreamHeadersDraft) {
  return JSON.stringify({ global: headersToRecord(config.global) });
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
  return null;
}
