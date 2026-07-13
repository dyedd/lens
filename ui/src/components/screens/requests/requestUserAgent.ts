import { titleForLocale } from "@/lib/I18nContext";

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

/** Extract a normalized platform label from a user-agent string. */
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
