import { describe, expect, it } from "vitest";
import { validateNumericSettings } from "./numericSettingsValidation";
import { createEmptySettingsDraft } from "./settingsDraft";
import { validateUpstreamHeadersConfig } from "./upstreamHeaderConfig";
import { validateUpstreamParamOverrideConfig } from "./upstreamParamOverride";

function validSettingsDraft() {
  const draft = createEmptySettingsDraft();
  draft.authAccessTokenMinutes = "60";
  draft.maxRequestBodyBytes = "1048576";
  return draft;
}

describe("validateNumericSettings", () => {
  it("accepts configured range boundaries and finite decimals", () => {
    const draft = validSettingsDraft();
    draft.authAccessTokenMinutes = "525600";
    draft.healthPenaltyWeight = "1";
    draft.firstTokenTimeoutSeconds = "1e2";

    expect(validateNumericSettings(draft, "en-US")).toEqual({});
  });

  it.each([
    ["authAccessTokenMinutes", "0"],
    ["authAccessTokenMinutes", "525601"],
    ["maxRequestBodyBytes", "1.5"],
    ["healthPenaltyWeight", "1.01"],
    ["firstTokenTimeoutSeconds", "Infinity"],
  ] as const)("rejects an out-of-range or invalid %s value", (key, value) => {
    const draft = validSettingsDraft();
    draft[key] = value;

    expect(validateNumericSettings(draft, "en-US")[key]).toBeTruthy();
  });
});

describe("validateUpstreamHeadersConfig", () => {
  it("allows an empty draft row and rejects a value without a name", () => {
    expect(
      validateUpstreamHeadersConfig(
        { rules: [{ key: "", value: "", action: "override" }] },
        "en-US",
      ),
    ).toBeNull();
    expect(
      validateUpstreamHeadersConfig(
        { rules: [{ key: "", value: "token", action: "override" }] },
        "en-US",
      ),
    ).toBe("Header names are required.");
  });
});

describe("validateUpstreamParamOverrideConfig", () => {
  it.each([
    [{ path: "model", action: "set", value: "replacement" }],
    [{ path: "model.name", action: "delete", value: "" }],
  ] as const)("rejects model overrides", (rule) => {
    expect(
      validateUpstreamParamOverrideConfig({ rules: [rule] }, "en-US"),
    ).toBe("Parameter rules cannot override model.");
  });

  it("requires a value for set rules", () => {
    expect(
      validateUpstreamParamOverrideConfig(
        { rules: [{ path: "temperature", action: "set", value: " " }] },
        "en-US",
      ),
    ).toBe("Parameter values are required.");
  });
});
