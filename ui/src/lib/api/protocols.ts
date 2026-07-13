export type ProtocolKind =
  | "openai_chat"
  | "openai_responses"
  | "openai_embedding"
  | "openai_image"
  | "rerank"
  | "anthropic"
  | "gemini";

let supportedConversions: Partial<Record<ProtocolKind, ProtocolKind[]>> = {};

/** Replaces the client-side protocol conversion reachability matrix. */
export function hydrateProtocolConversions(
  matrix: Record<string, string[]> | undefined,
): void {
  if (!matrix) {
    console.warn(
      "Protocol conversion matrix not provided. UI filtering may be incorrect.",
    );
    return;
  }
  const next: Partial<Record<ProtocolKind, ProtocolKind[]>> = {};
  for (const [channel, targets] of Object.entries(matrix)) {
    const reachable = targets.filter(
      (target): target is ProtocolKind => target !== channel,
    ) as ProtocolKind[];
    if (reachable.length > 0) next[channel as ProtocolKind] = reachable;
  }
  supportedConversions = next;
}

/** Reports whether a channel protocol can serve a target protocol. */
export function canReachProtocol(
  channelProtocol: ProtocolKind,
  groupProtocol: ProtocolKind,
): boolean {
  if (channelProtocol === groupProtocol) return true;
  return (
    supportedConversions[channelProtocol]?.includes(groupProtocol) ?? false
  );
}

/** Reports whether an item protocol can serve any selected protocol. */
export function isItemValidForProtocols(
  itemProtocol: ProtocolKind,
  selectedProtocols: ProtocolKind[],
): boolean {
  return selectedProtocols.some((protocol) =>
    canReachProtocol(itemProtocol, protocol),
  );
}
