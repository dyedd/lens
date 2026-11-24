// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { ADMIN_TOKEN_KEY } from "../auth";
import { apiFetch, apiRequest } from "./client";

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
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

  it("sends the stored admin token only to admin-session endpoints", async () => {
    localStorage.setItem(ADMIN_TOKEN_KEY, "admin-token");
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/public/branding");
    await apiFetch("/admin/session", { method: "POST" });
    await apiFetch("/admin/app-info");

    expect(
      new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("authorization"),
    ).toBeNull();
    expect(
      new Headers(fetchMock.mock.calls[1]?.[1]?.headers).get("authorization"),
    ).toBeNull();
    expect(
      new Headers(fetchMock.mock.calls[2]?.[1]?.headers).get("authorization"),
    ).toBe("Bearer admin-token");
  });

  it("retains the HTTP status when reading an error body fails", async () => {
    const response = new Response(null, { status: 503 });
    const readError = new TypeError("response body interrupted");
    vi.spyOn(response, "text").mockRejectedValue(readError);
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(response));

    await expect(apiFetch("/admin/app-info")).rejects.toMatchObject({
      message: "Request failed with status 503",
      status: 503,
      cause: readError,
    });
  });

  it("preserves an aborted error-body read", async () => {
    const controller = new AbortController();
    const response = new Response(null, { status: 503 });
    const readError = new DOMException(
      "The operation was aborted",
      "AbortError",
    );
    vi.spyOn(response, "text").mockRejectedValue(readError);
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(response));
    const request = apiFetch("/admin/app-info", { signal: controller.signal });
    controller.abort();

    await expect(request).rejects.toBe(readError);
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

  it("retains the HTTP status when reading a successful body fails", async () => {
    const response = new Response(null, { status: 200 });
    const readError = new TypeError("response body interrupted");
    vi.spyOn(response, "text").mockRejectedValue(readError);
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(response));

    await expect(apiRequest("/admin/app-info")).rejects.toMatchObject({
      message: "Failed to read response from API",
      status: 200,
      cause: readError,
    });
  });

  it("preserves an aborted successful body read", async () => {
    const controller = new AbortController();
    const response = new Response(null, { status: 200 });
    const readError = new DOMException(
      "The operation was aborted",
      "AbortError",
    );
    vi.spyOn(response, "text").mockRejectedValue(readError);
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(response));
    const request = apiRequest("/admin/app-info", {
      signal: controller.signal,
    });
    controller.abort();

    await expect(request).rejects.toBe(readError);
  });
});
