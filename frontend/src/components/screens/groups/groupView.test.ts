import { describe, expect, it } from "vitest";
import { EMPTY_FORM } from "./groupTypes";
import { formToModelGroupPayload } from "./groupView";

describe("formToModelGroupPayload", () => {
  it("normalizes route group fields and context window", () => {
    const payload = formToModelGroupPayload({
      ...EMPTY_FORM,
      name: "  Default route  ",
      route_group_id: "  primary  ",
      match_regex: "  model-.*  ",
      match_regex_operator: "and",
      context_window: "128k",
    });

    expect(payload).toMatchObject({
      name: "Default route",
      route_group_id: "primary",
      match_regex: "",
      match_regex_operator: "or",
      context_window: 128_000,
    });
  });
});
