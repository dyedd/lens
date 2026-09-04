import { apiRequest } from "./client";
import type { ProtocolKind } from "./protocols";
import type { SiteBatchImportPayload, SiteBatchImportResult } from "./sites";

export type ForeignSiteFormat =
  | "lens"
  | "metapi"
  | "sub2api"
  | "ccload"
  | "all_api_hub"
  | "octopus"
  | "cli_proxy_api";

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
export async function previewForeignSiteImport(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<ForeignSiteImportPreview>("/admin/sites/import/preview", {
    method: "POST",
    body: formData,
  });
}

/** Imports the sites selected from a foreign backup preview. */
export async function importForeignSites(payload: SiteBatchImportPayload) {
  return apiRequest<SiteBatchImportResult>("/admin/sites/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
