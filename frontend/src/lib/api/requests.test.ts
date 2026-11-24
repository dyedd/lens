import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiError } from "./client";
import { requestLogDetail, requestLogPage } from "./requests";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request log response validation", () => {
  it("rejects a page whose entries are not request log items", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          Response.json({
            items: [{}],
            total: 1,
            limit: 25,
            offset: 0,
            channels: [],
            gateway_keys: [],
            gateway_has_multiple_keys: false,
            model_names: [],
          }),
        ),
      ),
    );

    await expect(requestLogPage(new URLSearchParams())).rejects.toMatchObject({
      message: "Invalid request log page response from API",
      status: 200,
    } satisfies Partial<ApiError>);
  });

  it("rejects request details without an attempts list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({}))),
    );

    await expect(requestLogDetail(42)).rejects.toMatchObject({
      message: "Invalid request log detail response from API",
      status: 200,
    } satisfies Partial<ApiError>);
  });
});
