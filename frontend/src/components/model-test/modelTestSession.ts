import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { apiRequest } from "@/lib/api/client";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { SettingItem } from "@/lib/api/settings";
import {
  MODEL_TEST_PROMPTS_SETTING_KEY,
  parseModelTestPrompts,
} from "@/lib/modelTestPrompts";

export type ModelTestDialogTarget = {
  modelName: string;
  upstreamName: string;
};

export function selectedModelTestProtocol(
  protocols: ProtocolKind[],
  selectedProtocol: ProtocolKind | null,
) {
  return selectedProtocol && protocols.includes(selectedProtocol)
    ? selectedProtocol
    : protocols.length === 1
      ? protocols[0]
      : null;
}

/** Loads the configured model-test prompts with defaults applied. */
export function useModelTestPrompts() {
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 5 * 60_000,
  });
  return useMemo(() => {
    if (!settings) return [];
    const mapping = new Map(settings.map((item) => [item.key, item.value]));
    return parseModelTestPrompts(mapping.get(MODEL_TEST_PROMPTS_SETTING_KEY));
  }, [settings]);
}
