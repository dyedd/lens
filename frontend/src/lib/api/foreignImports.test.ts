import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiError } from "./client";
import { previewForeignSiteImport } from "./foreignImports";
import { importSites } from "./sites";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("foreign import response validation", () => {
  it("accepts a valid preview and batch import result", async () => {
    const preview = {
      format: "octopus",
      sites: [
        {
          name: "Primary",
          enabled: true,
          tags: [],
          base_urls: ["https://api.example/v1"],
          credential_count: 1,
          model_count: 1,
          protocols: ["openai_chat"],
        },
      ],
      warnings: [],
      payload: { sites: [{ name: "Primary" }] },
    };
    const result = {
      committed: true,
      created_count: 1,
      skipped_count: 0,
      error_count: 0,
      not_committed_count: 0,
      items: [
        {
          index: 0,
          name: "Primary",
          status: "created",
          reason: "",
          site: { id: "site-1" },
          errors: [],
        },
      ],
    };
    const responses = [preview, result];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json(responses.shift()))),
    );

    await expect(
      previewForeignSiteImport(
        new File(["{}"], "backup.json"),
        new AbortController().signal,
      ),
    ).resolves.toEqual(preview);
    await expect(
      importSites({ sites: [{ name: "Primary" }] }),
    ).resolves.toEqual(result);
  });

  it("rejects malformed preview and import results before consumers read them", async () => {
    const malformedResponses = [
      { format: "octopus", sites: [], warnings: [], payload: { sites: null } },
      {
        committed: true,
        created_count: 2,
        skipped_count: 0,
        error_count: 0,
        not_committed_count: 0,
        items: [
          {
            index: 0,
            name: "Primary",
            status: "created",
            reason: "",
            errors: [],
          },
        ],
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json(malformedResponses.shift()))),
    );

    await expect(
      previewForeignSiteImport(
        new File(["{}"], "backup.json"),
        new AbortController().signal,
      ),
    ).rejects.toMatchObject({
      message: "Invalid channel import preview response from API",
      status: 200,
    } satisfies Partial<ApiError>);
    await expect(
      importSites({ sites: [{ name: "Primary" }] }),
    ).rejects.toMatchObject({
      message: "Invalid channel import response from API",
      status: 200,
    } satisfies Partial<ApiError>);
  });
});
