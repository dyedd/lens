import { useCallback, type Dispatch, type SetStateAction } from "react";

import { type UpstreamParamOverrideRuleDraft } from "@/lib/settingsTypes";

import { type SettingsDraft } from "./settingsDraft";
import {
  createEmptyUpstreamHeaderRule,
  type HeaderItem,
  type UpstreamHeaderRuleDraft,
  type UpstreamHeadersDraft,
} from "./upstreamHeaderConfig";
import { createEmptyUpstreamParamOverrideRule } from "./upstreamParamOverride";

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

  const addUpstreamHeaderRule = useCallback(() => {
    updateUpstreamHeadersConfig((current) => ({
      ...current,
      rules: [...current.rules, createEmptyUpstreamHeaderRule()],
    }));
  }, [updateUpstreamHeadersConfig]);

  const updateUpstreamHeaderRule = useCallback(
    (index: number, patch: Partial<UpstreamHeaderRuleDraft>) => {
      updateUpstreamHeadersConfig((current) => ({
        ...current,
        rules: current.rules.map((rule, currentIndex) =>
          currentIndex === index ? { ...rule, ...patch } : rule,
        ),
      }));
    },
    [updateUpstreamHeadersConfig],
  );

  const removeUpstreamHeaderRule = useCallback(
    (index: number) => {
      updateUpstreamHeadersConfig((current) => ({
        ...current,
        rules: current.rules.filter(
          (_, currentIndex) => currentIndex !== index,
        ),
      }));
    },
    [updateUpstreamHeadersConfig],
  );

  const moveUpstreamHeaderRule = useCallback(
    (index: number, direction: -1 | 1) => {
      updateUpstreamHeadersConfig((current) => {
        const nextIndex = index + direction;
        if (nextIndex < 0 || nextIndex >= current.rules.length) {
          return current;
        }
        const rules = [...current.rules];
        const rule = rules[index];
        if (!rule) {
          return current;
        }
        rules.splice(index, 1);
        rules.splice(nextIndex, 0, rule);
        return { ...current, rules };
      });
    },
    [updateUpstreamHeadersConfig],
  );

  const addRuleHeader = useCallback(
    (ruleIndex: number) => {
      updateUpstreamHeadersConfig((current) => ({
        ...current,
        rules: current.rules.map((rule, currentRuleIndex) =>
          currentRuleIndex === ruleIndex
            ? {
                ...rule,
                headers: [...rule.headers, { key: "", value: "" }],
              }
            : rule,
        ),
      }));
    },
    [updateUpstreamHeadersConfig],
  );

  const updateRuleHeader = useCallback(
    (ruleIndex: number, headerIndex: number, patch: Partial<HeaderItem>) => {
      updateUpstreamHeadersConfig((current) => ({
        ...current,
        rules: current.rules.map((rule, currentRuleIndex) =>
          currentRuleIndex === ruleIndex
            ? {
                ...rule,
                headers: rule.headers.map((header, currentHeaderIndex) =>
                  currentHeaderIndex === headerIndex
                    ? { ...header, ...patch }
                    : header,
                ),
              }
            : rule,
        ),
      }));
    },
    [updateUpstreamHeadersConfig],
  );

  const removeRuleHeader = useCallback(
    (ruleIndex: number, headerIndex: number) => {
      updateUpstreamHeadersConfig((current) => ({
        ...current,
        rules: current.rules.map((rule, currentRuleIndex) => {
          if (currentRuleIndex !== ruleIndex) {
            return rule;
          }
          const nextHeaders = rule.headers.filter(
            (_, currentHeaderIndex) => currentHeaderIndex !== headerIndex,
          );
          return {
            ...rule,
            headers: nextHeaders.length
              ? nextHeaders
              : [{ key: "", value: "" }],
          };
        }),
      }));
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

  const addParamOverrideRule = useCallback(() => {
    updateUpstreamParamOverrideConfig((current) => ({
      ...current,
      rules: [...current.rules, createEmptyUpstreamParamOverrideRule()],
    }));
  }, [updateUpstreamParamOverrideConfig]);

  const updateParamOverrideRule = useCallback(
    (index: number, patch: Partial<UpstreamParamOverrideRuleDraft>) => {
      updateUpstreamParamOverrideConfig((current) => ({
        ...current,
        rules: current.rules.map((rule, ruleIndex) =>
          ruleIndex === index ? { ...rule, ...patch } : rule,
        ),
      }));
    },
    [updateUpstreamParamOverrideConfig],
  );

  const removeParamOverrideRule = useCallback(
    (index: number) => {
      updateUpstreamParamOverrideConfig((current) => ({
        ...current,
        rules: current.rules.filter((_, ruleIndex) => ruleIndex !== index),
      }));
    },
    [updateUpstreamParamOverrideConfig],
  );

  const moveParamOverrideRule = useCallback(
    (index: number, direction: -1 | 1) => {
      updateUpstreamParamOverrideConfig((current) => {
        const nextIndex = index + direction;
        if (nextIndex < 0 || nextIndex >= current.rules.length) {
          return current;
        }
        const rules = [...current.rules];
        const rule = rules[index];
        if (!rule) {
          return current;
        }
        rules.splice(index, 1);
        rules.splice(nextIndex, 0, rule);
        return { ...current, rules };
      });
    },
    [updateUpstreamParamOverrideConfig],
  );

  return {
    setDraftValue,
    addGlobalHeader,
    updateGlobalHeader,
    removeGlobalHeader,
    addUpstreamHeaderRule,
    updateUpstreamHeaderRule,
    removeUpstreamHeaderRule,
    moveUpstreamHeaderRule,
    addRuleHeader,
    updateRuleHeader,
    removeRuleHeader,
    updateGlobalParamOverride,
    addParamOverrideRule,
    updateParamOverrideRule,
    removeParamOverrideRule,
    moveParamOverrideRule,
  };
}
