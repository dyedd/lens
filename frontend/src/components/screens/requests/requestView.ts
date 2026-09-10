import type {
  RequestLogFilterOption,
  RequestLogItem,
} from "@/lib/api/requests";
import type { SettingItem } from "@/lib/api/settings";
import { formatCredentialDisplayName } from "@/lib/credentialLabels";
import { titleForLocale } from "@/lib/I18nContext";

export const PAGE_SIZE = 20;
export const REQUEST_LOG_DETAIL_GC_TIME = 60_000;
export const RELAY_LOG_BODY_ENABLED = "relay_log_body_enabled";
export const EMPTY_FILTER_OPTION_ID = "n/a";

export type StatusFilter =
  | "all"
  | "running"
  | "success"
  | "failed"
  | "cancelled";
export type SortMode = "latest" | "cost" | "latency" | "tokens";

/** Read whether relay body logging is enabled from settings. */
export function parseRelayLogBodyEnabled(settings: SettingItem[] | undefined) {
  const item = settings?.find(
    (setting) => setting.key === RELAY_LOG_BODY_ENABLED,
  );
  return item?.value.trim().toLowerCase() === "true";
}

/** Format a millisecond duration for display. */
export function formatMs(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

export function formatMoney(value: number | null | undefined) {
  return `$${(value ?? 0).toFixed(6)}`;
}

/** Format a monetary value or a pending placeholder. */
export function formatMaybeMoney(
  value: number | null | undefined,
  pending: boolean,
) {
  if (pending && !value) return "-";
  return formatMoney(value);
}

export function formatCount(value: number) {
  return value.toLocaleString();
}

/** Format a count or a pending placeholder. */
export function formatMaybeCount(value: number, pending: boolean) {
  if (pending && !value) return "-";
  return formatCount(value);
}

export function shortenGatewayKeyId(value?: string | null) {
  if (!value) return "";
  if (value.length <= 10) return value;
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

/** Format the gateway API key label for a request log. */
export function formatGatewayKeyLabel(
  item: Pick<RequestLogItem, "gateway_key_id" | "gateway_key_remark">,
  locale: "zh-CN" | "en-US",
) {
  return (
    item.gateway_key_remark?.trim() ||
    shortenGatewayKeyId(item.gateway_key_id) ||
    titleForLocale(locale, "未绑定 API Key", "No API key")
  );
}

export function formatInternalCredentialLabel(
  item: Pick<
    RequestLogItem,
    "credential_id" | "credential_name" | "credential_number"
  >,
  locale: "zh-CN" | "en-US",
) {
  const credentialName = item.credential_name?.trim();
  if (item.credential_number > 0 || credentialName) {
    return formatCredentialDisplayName(
      credentialName,
      item.credential_number,
      locale,
    );
  }
  return credentialName || shortenGatewayKeyId(item.credential_id);
}

/** Format a channel credential label for a request log. */
export function formatChannelCredentialLabel(
  item: Pick<
    RequestLogItem,
    | "channel_id"
    | "channel_name"
    | "credential_id"
    | "credential_name"
    | "credential_number"
    | "channel_has_multiple_credentials"
  >,
  locale: "zh-CN" | "en-US",
) {
  const channelLabel =
    item.channel_name ||
    item.channel_id ||
    titleForLocale(locale, "未选择渠道", "No channel");
  if (!item.channel_has_multiple_credentials) return channelLabel;
  const credentialLabel = formatInternalCredentialLabel(item, locale);
  return credentialLabel
    ? `${channelLabel} | ${credentialLabel}`
    : channelLabel;
}

/** Format a localized channel filter option label. */
export function channelFilterOptionLabel(
  item: RequestLogFilterOption,
  locale: "zh-CN" | "en-US",
) {
  if (item.id === EMPTY_FILTER_OPTION_ID) {
    return titleForLocale(locale, "未选择渠道", "No channel");
  }
  return item.label.trim() || item.id;
}

/** Format a localized gateway key filter option label. */
export function gatewayKeyFilterOptionLabel(
  item: RequestLogFilterOption,
  locale: "zh-CN" | "en-US",
) {
  if (item.id === EMPTY_FILTER_OPTION_ID) {
    return titleForLocale(locale, "未绑定 API Key", "No API key");
  }
  const label = item.label.trim();
  return label && label !== item.id ? label : shortenGatewayKeyId(item.id);
}

/** Preserve a selected filter identifier when it is absent from options. */
export function filterOptionsWithSelected(
  items: RequestLogFilterOption[] | undefined,
  selectedId: string | null,
) {
  const options = items ?? [];
  if (!selectedId || options.some((item) => item.id === selectedId)) {
    return options;
  }
  return [{ id: selectedId, label: selectedId }, ...options];
}

/** Resolve the best available model group name for a request. */
export function getResolvedGroupName(
  item: Pick<
    RequestLogItem,
    "requested_group_name" | "resolved_group_name" | "upstream_model_name"
  >,
) {
  return (
    item.resolved_group_name ||
    item.requested_group_name ||
    item.upstream_model_name ||
    "n/a"
  );
}

/** Build the displayed requested-to-upstream model chain. */
export function getModelChain(
  item: Pick<
    RequestLogItem,
    "requested_group_name" | "resolved_group_name" | "upstream_model_name"
  >,
) {
  const requested = item.requested_group_name?.trim();
  const resolved = item.resolved_group_name?.trim();
  if (requested && resolved && requested !== resolved) {
    return `${requested} -> ${resolved}`;
  }
  return resolved || requested || item.upstream_model_name || "n/a";
}

/** Return the secondary resolved or upstream model label when distinct. */
export function getSecondaryModelName(
  item: Pick<
    RequestLogItem,
    "requested_group_name" | "resolved_group_name" | "upstream_model_name"
  >,
) {
  const resolved = item.resolved_group_name?.trim();
  const upstream = item.upstream_model_name?.trim();
  return upstream && upstream !== resolved ? upstream : null;
}

/** Build compact pagination items around the current page. */
export function buildPaginationItems(currentPage: number, totalPages: number) {
  if (totalPages <= 1) return [1];
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }
  if (currentPage <= 2) return [1, 2, 3, "ellipsis", totalPages] as const;
  if (currentPage >= totalPages - 2) {
    return [1, "ellipsis", totalPages - 2, totalPages - 1, totalPages] as const;
  }
  return [
    1,
    "ellipsis",
    currentPage,
    currentPage + 1,
    "ellipsis",
    totalPages,
  ] as const;
}

export const HIDDEN_USER_AGENT_PRODUCTS = new Set([
  "applewebkit",
  "mozilla",
  "vscode",
]);
export const PREFERRED_USER_AGENT_PRODUCTS = [
  "codex-tui",
  "claude-cli",
  "edg",
  "chrome",
  "firefox",
  "safari",
] as const;
export const USER_AGENT_PRODUCT_PATTERN =
  /\b([A-Za-z][A-Za-z0-9._-]*)\/([^\s;)]+)/g;
export const USER_AGENT_PLATFORM_PATTERN =
  /\b(Windows(?:\s+NT)?|Macintosh|Mac OS(?:\s+X)?|macOS|Ubuntu|Linux|Android|iPhone|iPad|iPod)\b/i;

export type UserAgentProduct = {
  name: string;
  version: string;
};

/** Format a user-agent product name for display. */
export function formatUserAgentProductName(value: string) {
  if (value.toLowerCase() === "edg") return "Edge";
  return value;
}

/** Parse visible products from a raw user-agent string. */
export function parseUserAgentProducts(raw: string) {
  return Array.from(raw.matchAll(USER_AGENT_PRODUCT_PATTERN))
    .map<UserAgentProduct>((match) => ({
      name: match[1],
      version: match[2],
    }))
    .filter(
      (product) => !HIDDEN_USER_AGENT_PRODUCTS.has(product.name.toLowerCase()),
    );
}

/** Select the preferred client product from parsed user-agent products. */
export function selectUserAgentProduct(products: UserAgentProduct[]) {
  for (const preferredName of PREFERRED_USER_AGENT_PRODUCTS) {
    const matchedProduct = products.find(
      (product) => product.name.toLowerCase() === preferredName,
    );
    if (matchedProduct) return matchedProduct;
  }
  return products[0] ?? null;
}

/** Extract a platform label from a user-agent string. */
export function formatUserAgentPlatform(raw: string) {
  const match = raw.match(USER_AGENT_PLATFORM_PATTERN);
  const platform = match?.[1]?.toLowerCase();

  if (!platform) return null;
  if (platform.startsWith("windows")) return "Windows";
  if (
    platform === "macintosh" ||
    platform.startsWith("mac os") ||
    platform === "macos"
  ) {
    return "macOS";
  }
  if (platform === "ubuntu") return "Ubuntu";
  if (platform === "linux") return "Linux";
  if (["iphone", "ipad", "ipod"].includes(platform)) return "iOS";
  if (platform === "android") return "Android";
  return null;
}

/** Format a user agent into a localized client and platform label. */
export function formatUserAgentDisplay(
  value: string,
  locale: "zh-CN" | "en-US",
) {
  const raw = value.trim();
  const parts: string[] = [];
  const client = selectUserAgentProduct(parseUserAgentProducts(raw));
  const platform = formatUserAgentPlatform(raw);

  if (client) {
    parts.push(`${formatUserAgentProductName(client.name)}/${client.version}`);
  } else {
    parts.push(titleForLocale(locale, "未知客户端", "Unknown client"));
  }

  if (platform) parts.push(platform);

  return parts.join(" · ");
}

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

/** Parse a JSON value and return null when parsing fails. */
export function tryParseJsonValue(value: string) {
  try {
    return JSON.parse(value) as JsonValue;
  } catch {
    return null;
  }
}

export function formatHtmlErrorContent(value: string) {
  return value
    .replace(/>\s*</g, ">\n<")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(
      /<\/(p|div|section|article|header|footer|main|h1|h2|h3|h4|h5|h6|li|ul|ol|pre|code)>/gi,
      "$&\n",
    )
    .trim();
}

export function formatJsonErrorContent(prefix: string, value: JsonValue) {
  const jsonText = JSON.stringify(value, null, 2);
  if (!jsonText) return prefix.trim() || null;
  return jsonText;
}

/** Extract the first string value of common error shapes, or null. */
function knownErrorMessage(value: JsonValue): string | null {
  if (typeof value === "string") return value;
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const container =
    typeof value.error === "object" &&
    value.error !== null &&
    !Array.isArray(value.error)
      ? value.error
      : value;
  for (const key of ["message", "msg", "detail", "error"]) {
    const candidate = container[key];
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }
  return null;
}

/** Parse a payload as JSON, tolerating a text prefix before the object. */
function parseErrorJson(raw: string): JsonValue | null {
  const direct = tryParseJsonValue(raw);
  if (direct !== null) return direct;
  const jsonStart = raw.indexOf("{");
  if (jsonStart > 0) return tryParseJsonValue(raw.slice(jsonStart));
  return null;
}

/** Collapse a JSON or text error into a single display line. */
export function formatErrorSummary(value: string | null | undefined) {
  const raw = value?.trim();
  if (!raw) return null;
  const known = knownErrorMessage(parseErrorJson(raw));
  if (known) return known;
  const display = formatErrorDisplay(value);
  if (!display) return null;
  if (!display.includes("\n")) return display;
  return (
    display
      .split("\n")
      .map((line) => line.trim())
      .find(Boolean) || display
  );
}

/** Format JSON, HTML, or text errors for readable display. */
export function formatErrorDisplay(value: string | null | undefined) {
  const raw = value?.trim();
  if (!raw) return null;

  const directParsed = tryParseJsonValue(raw);
  if (directParsed !== null) return formatJsonErrorContent("", directParsed);

  const jsonStart = raw.indexOf("{");
  if (jsonStart > 0) {
    const nestedParsed = tryParseJsonValue(raw.slice(jsonStart));
    if (nestedParsed !== null) {
      return formatJsonErrorContent(raw.slice(0, jsonStart), nestedParsed);
    }
  }

  if (/<!doctype html|<html|<head|<body|<title/i.test(raw)) {
    return formatHtmlErrorContent(raw);
  }
  return raw;
}
