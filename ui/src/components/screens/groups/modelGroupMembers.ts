import type { ModelGroup, ProtocolKind } from "@/lib/api";
import type { GroupDisplayMember, ProtocolMeta } from "./modelGroupUtils";

export const PROTOCOL_SUFFIXES: ProtocolKind[] = [
  "openai_chat",
  "openai_responses",
  "openai_embedding",
  "openai_image",
  "rerank",
  "anthropic",
  "gemini",
];

/** Remove a known protocol suffix from a runtime channel identifier. */
export function protocolConfigIdFromChannelId(channelId: string): string {
  for (const suffix of PROTOCOL_SUFFIXES) {
    if (channelId.endsWith(`_${suffix}`)) {
      return channelId.slice(0, channelId.length - suffix.length - 1);
    }
  }
  return channelId;
}

/** Build the stable key used to fold equivalent model members. */
export function modelFoldKey(
  protocolConfigId: string,
  credentialId: string,
  modelName: string,
): string {
  return `${protocolConfigId}::${credentialId}::${modelName}`;
}

/** Build the lookup key for credential and model availability. */
export function modelAvailabilityKey(
  item: Pick<ModelGroup["items"][number], "credential_id" | "model_name">,
) {
  return JSON.stringify([item.credential_id, item.model_name]);
}

function isGroupItemUpstreamAvailable(
  item: Pick<
    ModelGroup["items"][number],
    "channel_id" | "credential_id" | "model_name"
  >,
  channelMap: Map<string, ProtocolMeta>,
  upstreamAvailabilityReady: boolean,
) {
  if (!upstreamAvailabilityReady) return true;
  const channel = channelMap.get(item.channel_id);
  if (!channel) return false;
  if (!channel.enabled) return false;
  const credentialEnabled = channel.credential_enabled_by_id.get(
    item.credential_id,
  );
  if (credentialEnabled !== true) {
    return false;
  }
  return channel.model_enabled_by_key.get(modelAvailabilityKey(item)) === true;
}

/** Fold stored group items into display members with availability state. */
export function buildGroupDisplayMembers(
  items: ModelGroup["items"],
  channelMap: Map<string, ProtocolMeta>,
  upstreamAvailabilityReady: boolean,
): GroupDisplayMember[] {
  const orderMap = new Map<string, number>();
  const memberMap = new Map<string, GroupDisplayMember>();

  for (const item of items) {
    const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
    const key = modelFoldKey(
      protocolConfigId,
      item.credential_id,
      item.model_name,
    );
    const channel = channelMap.get(item.channel_id);
    const channelName = channel?.name || item.channel_name || item.channel_id;
    const protocol = item.protocol || channel?.protocol;
    const upstreamAvailable = isGroupItemUpstreamAvailable(
      item,
      channelMap,
      upstreamAvailabilityReady,
    );

    if (!memberMap.has(key)) {
      orderMap.set(key, orderMap.size);
      memberMap.set(key, {
        key,
        model_name: item.model_name,
        credential_name: item.credential_name,
        credential_number: item.credential_number,
        channel_names: [],
        protocols: [],
        items: [],
        enabled: false,
        isRoutable: false,
        isUnavailable: false,
      });
    }

    const member = memberMap.get(key)!;
    member.items.push(item);
    if (item.enabled) member.enabled = true;
    if (item.enabled && upstreamAvailable) member.isRoutable = true;
    if (!upstreamAvailable) member.isUnavailable = true;
    if (channelName && !member.channel_names.includes(channelName)) {
      member.channel_names.push(channelName);
    }
    if (protocol && !member.protocols.includes(protocol)) {
      member.protocols.push(protocol);
    }
  }

  return Array.from(orderMap.entries())
    .sort((a, b) => a[1] - b[1])
    .map(([key]) => memberMap.get(key)!);
}
