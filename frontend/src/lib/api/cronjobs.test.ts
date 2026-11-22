import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiError } from "./client";
import { requestCronjobs, runCronjob, updateCronjob } from "./cronjobs";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("cronjob response validation", () => {
  it("rejects a successful list response with the wrong shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({}))),
    );

    await expect(requestCronjobs()).rejects.toMatchObject({
      message: "Invalid scheduled tasks response from API",
      status: 200,
    } satisfies Partial<ApiError>);
  });

  it("rejects malformed update and run responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({}))),
    );

    await expect(
      updateCronjob("task", {
        enabled: true,
        schedule_type: "interval",
        interval_hours: 1,
        run_at_time: null,
        weekdays: [],
      }),
    ).rejects.toMatchObject({ status: 200 });
    await expect(runCronjob("task")).rejects.toMatchObject({ status: 200 });
  });
});
