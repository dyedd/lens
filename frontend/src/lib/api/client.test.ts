import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, apiRequest } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api response errors", () => {
  it("keeps malformed JSON error text and the parse cause", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response("upstream returned an invalid gateway reply", {
            status: 502,
            headers: { "content-type": "application/json" },
          }),
        ),
      ),
    );

    await expect(apiFetch("/health")).rejects.toMatchObject({
      message: "upstream returned an invalid gateway reply",
      status: 502,
      cause: expect.any(SyntaxError),
    });
  });

  it("parses valid API error messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              error: { type: "invalid", message: "Bad request" },
            }),
            {
              status: 400,
              headers: { "content-type": "application/json" },
            },
          ),
        ),
      ),
    );

    await expect(apiFetch("/health")).rejects.toMatchObject({
      message: "Bad request",
      status: 400,
      errorType: "invalid",
    });
  });

  it("keeps strict parsing for successful API responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("{", { status: 200 }))),
    );

    await expect(apiRequest("/health")).rejects.toMatchObject({
      message: expect.stringContaining("Invalid JSON response from API"),
      status: 200,
      cause: expect.any(SyntaxError),
    });
  });
});
