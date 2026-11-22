import { ApiError, apiRequest, isRecord } from "./client";
import { isProtocolKind, type ProtocolKind } from "./protocols";
import type { SiteBatchImportPayload } from "./sites";

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
  protocols: ProtocolKind[];
};

export type ForeignSiteImportPreview = {
  format: ForeignSiteFormat;
  sites: ForeignSitePreview[];
  warnings: string[];
  payload: SiteBatchImportPayload | null;
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
        typeof site.credential_count === "number" &&
        typeof site.model_count === "number" &&
        Array.isArray(site.protocols) &&
        site.protocols.every(isProtocolKind),
    )
  ) {
    return false;
  }
  return (
    value.payload === null ||
    (isRecord(value.payload) &&
      Array.isArray(value.payload.sites) &&
      value.payload.sites.length === value.sites.length &&
      value.payload.sites.every(isRecord))
  );
}
