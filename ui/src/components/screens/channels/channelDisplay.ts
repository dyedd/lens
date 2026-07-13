import type { Site } from "@/lib/api";
import { protocolLabel } from "@/lib/protocols";

/** Formats a cooldown duration as compact hours, minutes, and seconds. */
export function formatCooldownDuration(seconds: number) {
  const value = Math.max(Math.floor(seconds), 0);
  if (value < 60) return `${value}s`;

  const minutes = Math.floor(value / 60);
  const remainingSeconds = value % 60;
  if (minutes < 60) {
    return remainingSeconds
      ? `${minutes}m ${remainingSeconds}s`
      : `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

export function modelBadgeClassName(enabled: boolean) {
  return enabled
    ? "inline-flex h-8 items-center gap-2 rounded-full border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-muted"
    : "inline-flex h-8 items-center gap-2 rounded-full border bg-muted/40 px-3 text-sm font-medium text-muted-foreground";
}

/** Returns the unique protocols configured for a site. */
export function siteProtocols(site: Site) {
  return Array.from(
    new Set(
      site.protocols.flatMap((protocolConfig) => protocolConfig.protocols),
    ),
  );
}

/** Builds a localized protocol summary for a site. */
export function siteSubtitle(site: Site, locale: "zh-CN" | "en-US") {
  return siteProtocols(site)
    .map((p) => protocolLabel(p, locale))
    .join(" / ");
}

/** Builds a compact summary of a site's configured base URLs. */
export function siteEndpointSummary(site: Site, locale: string = "zh-CN") {
  const enabled = site.base_urls.filter((item) => item.enabled);
  const firstUrl = enabled[0]?.url || site.base_urls[0]?.url || "";
  const extraCount =
    enabled.length > 1
      ? enabled.length - 1
      : site.base_urls.length > 1
        ? site.base_urls.length - 1
        : 0;
  if (extraCount > 0) {
    const suffix =
      locale === "zh-CN" ? ` + ${extraCount}个地址` : ` + ${extraCount} more`;
    return firstUrl + suffix;
  }
  return firstUrl;
}

/** Counts enabled model entries across a site's protocol configurations. */
export function siteModelCount(site: Site) {
  return site.protocols.reduce(
    (total, protocolConfig) =>
      total + protocolConfig.models.filter((model) => model.enabled).length,
    0,
  );
}

/** Reports whether a site has at least one enabled protocol configuration. */
export function isSiteEnabled(site: Site) {
  return site.protocols.some((protocolConfig) => protocolConfig.enabled);
}

/** Builds ordered favicon candidates for a valid site URL. */
export function getSiteFaviconCandidates(url: string) {
  try {
    const parsed = new URL(url);
    return [
      `${parsed.origin}/favicon.ico`,
      `https://www.google.com/s2/favicons?domain=${parsed.hostname}&sz=64`,
    ];
  } catch {
    return [];
  }
}
