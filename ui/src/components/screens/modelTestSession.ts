"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest, type ProtocolKind, type SettingItem } from "@/lib/api";
import {
  MODEL_TEST_PROMPTS_SETTING_KEY,
  parseModelTestPrompts,
} from "@/lib/modelTestPrompts";

export type ModelTestDialogTarget = {
  modelName: string;
  source: string;
  protocols: ProtocolKind[];
};

/** Selects a valid test protocol with a deterministic fallback. */
export function selectedModelTestProtocol(
  protocols: ProtocolKind[],
  selectedProtocol: ProtocolKind | null,
) {
  return selectedProtocol && protocols.includes(selectedProtocol)
    ? selectedProtocol
    : (protocols[0] ?? null);
}

/** Loads the configured model-test prompts with defaults applied. */
export function useModelTestPrompts() {
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 5 * 60_000,
  });
  return useMemo(() => {
    const mapping = new Map(
      (settings ?? []).map((item) => [item.key, item.value]),
    );
    return parseModelTestPrompts(mapping.get(MODEL_TEST_PROMPTS_SETTING_KEY));
  }, [settings]);
}
