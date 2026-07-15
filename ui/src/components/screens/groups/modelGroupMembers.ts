import type { ModelGroup } from "@/lib/api";
import type { GroupDisplayMember } from "./modelGroupUtils";

/** Build the stable key used to fold equivalent model members. */
export function modelFoldKey(
  protocolConfigId: string,
  credentialId: string,
  modelName: string,
): string {
  return `${protocolConfigId}::${credentialId}::${modelName}`;
}

/** Fold stored group items into display members with availability state. */
export function buildGroupDisplayMembers(
  items: ModelGroup["items"],
): GroupDisplayMember[] {
  const orderMap = new Map<string, number>();
  const memberMap = new Map<string, GroupDisplayMember>();

  for (const item of items) {
    const key = modelFoldKey(
      item.protocol_config_id,
      item.credential_id,
      item.model_name,
    );
    const channelName = item.channel_name || item.channel_id;

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
        enabled_item_count: 0,
        disabled_item_count: 0,
        ready_item_count: 0,
        invalid_item_count: 0,
        unavailable_item_count: 0,
      });
    }

    const member = memberMap.get(key)!;
    member.items.push(item);
    if (item.enabled) member.enabled_item_count += 1;
    else member.disabled_item_count += 1;
    if (item.state === "ready") member.ready_item_count += 1;
    if (item.state === "invalid") member.invalid_item_count += 1;
    if (item.state === "unavailable") member.unavailable_item_count += 1;
    if (channelName && !member.channel_names.includes(channelName)) {
      member.channel_names.push(channelName);
    }
    if (item.protocol && !member.protocols.includes(item.protocol)) {
      member.protocols.push(item.protocol);
    }
  }

  return Array.from(orderMap.entries())
    .sort((a, b) => a[1] - b[1])
    .map(([key]) => memberMap.get(key)!);
}
