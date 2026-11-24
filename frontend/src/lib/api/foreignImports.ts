import { ApiError, apiRequest, isRecord } from "./client";

const FOREIGN_SITE_FORMATS = [
  "lens",
  "metapi",
  "sub2api",
  "ccload",
  "all_api_hub",
  "octopus",
  "cli_proxy_api",
] as const;
export type ForeignSiteFormat = (typeof FOREIGN_SITE_FORMATS)[number];

export type ForeignSitePreview = {
  name: string;
  enabled: boolean;
  tags: string[];
  base_urls: string[];
  credential_count: number;
  model_count: number;
};

export type ForeignSiteImportPreview = {
  format: ForeignSiteFormat;
  sites: ForeignSitePreview[];
  warnings: string[];
  payload: { sites: unknown[] } | null;
};

/** Uploads a foreign backup file and previews the sites it would import. */
export async function previewForeignSiteImport(
  file: File,
  signal: AbortSignal,
): Promise<ForeignSiteImportPreview> {
  const formData = new FormData();
  formData.append("file", file);
  const value = await apiRequest<unknown>("/admin/sites/import/preview", {
    method: "POST",
    body: formData,
    signal,
  });
  if (!isForeignSiteImportPreview(value)) {
    throw new ApiError("Invalid channel import preview response from API", 200);
  }
  return value;
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
}

function isForeignSiteImportPreview(
  value: unknown,
): value is ForeignSiteImportPreview {
  if (
    !isRecord(value) ||
    !FOREIGN_SITE_FORMATS.some((format) => format === value.format) ||
    !isStringArray(value.warnings) ||
    !Array.isArray(value.sites) ||
    !value.sites.every(
      (site) =>
        isRecord(site) &&
        typeof site.name === "string" &&
        typeof site.enabled === "boolean" &&
        isStringArray(site.tags) &&
        isStringArray(site.base_urls) &&
        isCount(site.credential_count) &&
        isCount(site.model_count),
    )
  ) {
    return false;
  }
  const { sites, payload } = value;
  return payload === null
    ? sites.length === 0
    : isRecord(payload) &&
        Array.isArray(payload.sites) &&
        payload.sites.length > 0 &&
        payload.sites.length === sites.length &&
        payload.sites.every(
          (site, index) => isRecord(site) && site.name === sites[index].name,
        );
}

function isCount(value: unknown) {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}
