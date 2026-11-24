import { describe, expect, it } from "vitest";
import { getLoginAccessToken } from "./auth";

describe("getLoginAccessToken", () => {
  it("returns a trimmed non-empty token", () => {
    expect(getLoginAccessToken({ access_token: " token-value " })).toBe(
      "token-value",
    );
  });

  it.each([
    null,
    undefined,
    "token-value",
    {},
    { access_token: "" },
    { access_token: "   " },
    { access_token: 1 },
  ])("rejects malformed login responses %#", (response) => {
    expect(getLoginAccessToken(response)).toBeNull();
  });
});
