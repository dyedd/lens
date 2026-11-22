import { describe, expect, it } from "vitest";
import { parseBackupPreview } from "./backupPreview";

describe("parseBackupPreview", () => {
  it("counts supported backup collections and imported statistics", () => {
    const preview = parseBackupPreview(
      JSON.stringify({
        exported_at: "2026-11-22T00:00:00Z",
        lens_version: "1.2.3",
        include_request_logs: true,
        settings: [{}],
        sites: [{}, {}],
        groups: [{}],
        model_prices: [],
        cronjobs: [{}],
        gateway_api_keys: [{}],
        request_logs: [{}, {}],
        stats: {
          imported_total: { requests: 1 },
          imported_daily: [{}],
          request_daily: [{}],
          model_daily: [],
          attribution_hourly: [{}],
        },
      }),
    );

    expect(preview).toMatchObject({
      exported_at: "2026-11-22T00:00:00Z",
      lens_version: "1.2.3",
      include_request_logs: true,
      include_gateway_api_keys: false,
      counts: {
        settings: 1,
        sites: 2,
        groups: 1,
        model_prices: 0,
        cronjobs: 1,
        gateway_api_keys: 1,
        request_logs: 2,
        stats: 4,
      },
    });
  });

  it("rejects a non-object backup payload", () => {
    expect(() => parseBackupPreview("[]")).toThrow("Invalid backup file");
  });
});
