import { type Dispatch, type SetStateAction, useCallback } from "react";

import type { SettingsDraft } from "./settingsDraft";
import type { HeaderItem, UpstreamHeadersDraft } from "./upstreamHeaderConfig";

/** Provide stable immutable update actions for a settings draft. */
export function useSettingsDraftActions(
  setDraft: Dispatch<SetStateAction<SettingsDraft>>,
) {
  const setDraftValue = useCallback(
    <Key extends keyof SettingsDraft>(key: Key, value: SettingsDraft[Key]) => {
      setDraft((current) => ({ ...current, [key]: value }));
    },
    [setDraft],
  );

  const updateUpstreamHeadersConfig = useCallback(
    (updater: (current: UpstreamHeadersDraft) => UpstreamHeadersDraft) => {
      setDraft((current) => ({
        ...current,
        upstreamHeadersConfig: updater(current.upstreamHeadersConfig),
      }));
    },
    [setDraft],
  );

  const addGlobalHeader = useCallback(() => {
    updateUpstreamHeadersConfig((current) => ({
      ...current,
      global: [...current.global, { key: "", value: "" }],
    }));
  }, [updateUpstreamHeadersConfig]);

  const updateGlobalHeader = useCallback(
    (index: number, patch: Partial<HeaderItem>) => {
      updateUpstreamHeadersConfig((current) => ({
        ...current,
        global: current.global.map((header, currentIndex) =>
          currentIndex === index ? { ...header, ...patch } : header,
        ),
      }));
    },
    [updateUpstreamHeadersConfig],
  );

  const removeGlobalHeader = useCallback(
    (index: number) => {
      updateUpstreamHeadersConfig((current) => {
        const nextHeaders = current.global.filter(
          (_, currentIndex) => currentIndex !== index,
        );
        return {
          ...current,
          global: nextHeaders.length ? nextHeaders : [{ key: "", value: "" }],
        };
      });
    },
    [updateUpstreamHeadersConfig],
  );

  const updateUpstreamParamOverrideConfig = useCallback(
    (
      updater: (
        current: SettingsDraft["upstreamParamOverrideConfig"],
      ) => SettingsDraft["upstreamParamOverrideConfig"],
    ) => {
      setDraft((current) => ({
        ...current,
        upstreamParamOverrideConfig: updater(
          current.upstreamParamOverrideConfig,
        ),
      }));
    },
    [setDraft],
  );

  const updateGlobalParamOverride = useCallback(
    (value: string) => {
      updateUpstreamParamOverrideConfig((current) => ({
        ...current,
        global: value,
      }));
    },
    [updateUpstreamParamOverrideConfig],
  );

  return {
    setDraftValue,
    addGlobalHeader,
    updateGlobalHeader,
    removeGlobalHeader,
    updateGlobalParamOverride,
  };
}
