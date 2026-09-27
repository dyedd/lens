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

/** Keeps a valid choice, else the only protocol, else OpenAI Chat as model discovery assumes. */
export function selectedModelTestProtocol(
  protocols: ProtocolKind[],
  selectedProtocol: ProtocolKind | null,
): ProtocolKind | null {
  if (selectedProtocol && protocols.includes(selectedProtocol)) {
    return selectedProtocol;
  }
  if (protocols.length === 1) return protocols[0];
  return protocols.includes("openai_chat") ? "openai_chat" : null;
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
