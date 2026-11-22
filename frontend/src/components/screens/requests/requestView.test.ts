import { afterEach, describe, expect, it, vi } from "vitest";
import { formatErrorDisplay, formatErrorSummary } from "./requestView";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("request error formatting", () => {
  it("extracts a known message from common JSON error shapes", () => {
    expect(formatErrorSummary('{"error":{"message":"Upstream failed"}}')).toBe(
      "Upstream failed",
    );
  });

  it("formats prefixed JSON and preserves the parsed value", () => {
    expect(
      formatErrorDisplay('Gateway returned: {"code":503,"message":"Busy"}'),
    ).toBe(JSON.stringify({ code: 503, message: "Busy" }, null, 2));
  });

  it("does not parse the same JSON payload again for a summary fallback", () => {
    const parse = vi.spyOn(JSON, "parse");

    expect(formatErrorSummary('{"code":503}')).toBe("{");
    expect(parse).toHaveBeenCalledTimes(1);
  });

  it("formats HTML boundaries and leaves plain text unchanged", () => {
    expect(
      formatErrorDisplay(
        "<html><body><p>Failed</p><p>Try again</p></body></html>",
      ),
    ).toBe(
      "<html>\n<body>\n<p>Failed</p>\n\n<p>Try again</p>\n\n</body>\n</html>",
    );
    expect(formatErrorDisplay("Connection timed out")).toBe(
      "Connection timed out",
    );
    expect(formatErrorSummary("Connection timed out")).toBe(
      "Connection timed out",
    );
  });
});
