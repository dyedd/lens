import { describe, expect, it } from "vitest";
import {
  createEmptySettingsDraft,
  shouldAutoSaveSettingsDraft,
} from "./settingsDraft";

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
