import type { Site, SiteProtocolConfig } from "@/lib/api/sites";
import { protocolLabel } from "@/lib/protocols";

/** Returns the unique protocols configured for a site. */
function siteProtocols(site: Site) {
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

/** Reports whether a protocol configuration is enabled at every owning level. */
export function isSiteProtocolConfigEnabled(
  site: Site,
  protocolConfig: SiteProtocolConfig,
) {
  return site.enabled && protocolConfig.enabled;
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
