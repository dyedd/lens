import { describe, expect, it } from "vitest";
import {
  createEmptySettingsDraft,
  createSettingItems,
  createSettingsDraft,
  shouldAutoSaveSettingsDraft,
} from "./settingsDraft";

it("round trips privacy rules through automatic-save setting items", () => {
  const draft = createEmptySettingsDraft();
  draft.privacyConfig = {
    enabled: true,
    action: "block",
    categories: ["secrets"],
    words: ["internal"],
    regex_rules: [{ pattern: "customer-[0-9]+" }],
    exceptions: ["customer-42"],
  };
  expect(createSettingsDraft(createSettingItems(draft)).privacyConfig).toEqual(
    draft.privacyConfig,
  );
  expect(createSettingsDraft([]).privacyConfig.enabled).toBe(false);
});

describe("shouldAutoSaveSettingsDraft", () => {
  it("keeps a failed draft idle until it is explicitly retried", () => {
    const savedDraft = JSON.stringify(createEmptySettingsDraft());
    const changedDraft = {
      ...createEmptySettingsDraft(),
      siteName: "Lens Admin",
    };
    const changedDraftJson = JSON.stringify(changedDraft);

    expect(
      shouldAutoSaveSettingsDraft(changedDraft, savedDraft, changedDraftJson),
    ).toBe(false);
    expect(shouldAutoSaveSettingsDraft(changedDraft, savedDraft, null)).toBe(
      true,
    );
  });

  it("does not save a draft that already matches saved settings", () => {
    const draft = createEmptySettingsDraft();
    const savedDraft = JSON.stringify(draft);

    expect(shouldAutoSaveSettingsDraft(draft, savedDraft, null)).toBe(false);
  });
});
