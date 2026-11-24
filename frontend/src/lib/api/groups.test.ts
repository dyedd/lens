import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApiError } from "./client";
import { createModelGroup, requestModelGroups } from "./groups";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requestModelGroups", () => {
  it("returns groups with the expected response shape", async () => {
    const group = {
      id: "group-1",
      name: "Primary",
      client_protocols: ["openai_chat"],
      strategy: "failover",
      route_group_id: "",
      route_group_name: "",
      match_regex: "",
      match_regex_operator: "or",
      param_override: [],
      headers: [],
      fallback_group_ids: [],
      context_window: null,
      input_price_per_million: 0,
      image_input_price_per_million: 0,
      output_price_per_million: 0,
      cache_read_price_per_million: 0,
      cache_write_price_per_million: 0,
      image_price_per_image: 0,
      manual_override: false,
      pricing_mode: "free",
      items: [],
      excluded_items: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify([group]), { status: 200 })),
      ),
    );

    await expect(requestModelGroups()).resolves.toEqual([group]);
  });

  it("rejects a successful response with an invalid group shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("{}", { status: 200 }))),
    );

    await expect(requestModelGroups()).rejects.toEqual(
      expect.objectContaining({
        name: "ApiError",
        message: "Invalid model groups response from API",
        status: 200,
      } satisfies Partial<ApiError>),
    );
  });
});

describe("createModelGroup", () => {
  it("returns a non-empty id for a valid create response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({ id: "group-1" }))),
    );

    await expect(createModelGroup("{}")).resolves.toBe("group-1");
  });

  it.each([{}, { id: 1 }, { id: "  " }])(
    "rejects a successful response without a valid group id",
    async (response) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(() => Promise.resolve(Response.json(response))),
      );

      await expect(createModelGroup("{}")).rejects.toMatchObject({
        message: "Invalid created model group ID from API",
        status: 200,
      } satisfies Partial<ApiError>);
    },
  );
});
