import type { Site } from "@/lib/api/sites";
import type { FormBaseUrl, Locale } from "./channelTypes";

export function formatEndpointLabel(url: FormBaseUrl, locale: Locale) {
  const kind =
    url.kind === "default"
      ? locale === "zh-CN"
        ? "默认地址"
        : "Default"
      : url.kind === "models"
        ? locale === "zh-CN"
          ? "模型列表"
          : "Model list"
        : url.kind === "china"
          ? locale === "zh-CN"
            ? "国内地址"
            : "China"
          : url.kind;
  return `${kind} · ${formatBaseUrlLabel(url.url)}`;
}

/** Lists configured base URLs. */
export function siteEndpointUrls(site: Site) {
  return site.base_urls.map((item) => item.url.trim()).filter(Boolean);
}

/** Shortens a base URL for dense table cells. */
export function formatBaseUrlLabel(url: string) {
  return url.replace(/^https?:\/\//, "").replace(/\/+$/, "");
}

/** Builds a compact summary of a site's configured base URLs. */
export function siteEndpointSummary(site: Site, locale: string = "zh-CN") {
  const urls = siteEndpointUrls(site);
  if (urls.length <= 1) return urls[0] ?? "";
  const extraCount = urls.length - 1;
  const suffix =
    locale === "zh-CN" ? ` + ${extraCount}个地址` : ` + ${extraCount} more`;
  return urls[0] + suffix;
}

/** Counts enabled and total model entries for one site. */
export function siteModelCounts(site: Site) {
  let enabled = 0;
  let total = 0;
  for (const protocolConfig of site.protocols) {
    for (const model of protocolConfig.models) {
      total += 1;
      if (model.enabled) enabled += 1;
    }
  }
  return { enabled, total };
}
