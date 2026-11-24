import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiError } from "./client";
import { requestSettings } from "./settings";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requestSettings", () => {
  it("returns valid setting items", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify([{ key: "time_zone", value: "UTC" }]), {
            status: 200,
          }),
        ),
      ),
    );

    await expect(requestSettings()).resolves.toEqual([
      { key: "time_zone", value: "UTC" },
    ]);
  });

  it("rejects a successful response with an invalid settings shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("{}", { status: 200 }))),
    );

    await expect(requestSettings()).rejects.toEqual(
      expect.objectContaining({
        name: "ApiError",
        message: "Invalid settings response from API",
        status: 200,
      } satisfies Partial<ApiError>),
    );
  });
});
