import type { ProtocolKind } from "@/lib/api/protocols";
import type { ModelTestMode } from "@/lib/api/sites";

export type ModelTestDialogTarget = {
  modelName: string;
  upstreamName: string;
};

export function modelTestProtocols(
  protocols: ProtocolKind[],
  mode: ModelTestMode,
): ProtocolKind[] {
  if (mode === "codex") {
    return protocols.filter(
      (protocol) =>
        protocol === "openai_responses" || protocol === "openai_chat",
    );
  }
  if (mode === "claude") {
    return protocols.filter((protocol) => protocol === "anthropic");
  }
  return protocols;
}

export function selectedModelTestProtocol(
  protocols: ProtocolKind[],
  selectedProtocol: ProtocolKind | null,
  mode: ModelTestMode = "direct",
): ProtocolKind | null {
  const available = modelTestProtocols(protocols, mode);
  if (selectedProtocol && available.includes(selectedProtocol)) {
    return selectedProtocol;
  }
  if (available.length === 1) return available[0];
  if (mode === "codex" && available.includes("openai_responses")) {
    return "openai_responses";
  }
  return available.includes("openai_chat") ? "openai_chat" : null;
}
