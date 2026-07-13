import {
  isItemValidForProtocols,
  type ModelGroup,
  type ModelGroupCandidateItem,
  type ProtocolKind,
  type Site,
} from "@/lib/api";
import {
  buildGroupDisplayMembers,
  modelAvailabilityKey,
  modelFoldKey,
  protocolBaseUrl,
  protocolConfigIdFromChannelId,
  type CandidateChannelGroup,
  type FoldedMember,
  type FormItem,
  type GroupRow,
  type ProtocolMeta,
} from "./modelGroupUtils";

/** Build runtime channel metadata used by group availability checks. */
export function buildGroupChannelMap(sites: Site[]) {
  const channelMap = new Map<string, ProtocolMeta>();
  for (const site of sites) {
    const credentialEnabledById = new Map(
      site.credentials.map(
        (credential) =>
          [
            credential.id,
            credential.enabled && Boolean(credential.api_key.trim()),
          ] as const,
      ),
    );
    for (const protocolConfig of site.protocols) {
      const baseUrl = site.base_urls.find(
        (item) => item.id === protocolConfig.base_url_id,
      );
      const baseUrlValue =
        baseUrl?.url ?? protocolBaseUrl(site, protocolConfig.base_url_id);
      const isChannelEnabled =
        protocolConfig.enabled && Boolean(baseUrl?.enabled);
      for (const protocol of protocolConfig.protocols) {
        const runtimeChannelId = `${protocolConfig.id}_${protocol}`;
        const modelEnabledByKey = new Map(
          protocolConfig.models
            .filter((model) => model.protocol === protocol)
            .map(
              (model) => [modelAvailabilityKey(model), model.enabled] as const,
            ),
        );
        channelMap.set(runtimeChannelId, {
          id: runtimeChannelId,
          site_id: site.id,
          name: site.name,
          base_url: baseUrlValue,
          protocol,
          enabled: isChannelEnabled,
          credential_enabled_by_id: credentialEnabledById,
          model_enabled_by_key: modelEnabledByKey,
        });
      }
    }
  }
  return channelMap;
}

function buildExecutionRow(
  group: ModelGroup,
  channelMap: Map<string, ProtocolMeta>,
  isAvailabilityReady: boolean,
): GroupRow {
  const items = group.items
    .slice()
    .sort((left, right) => left.sort_order - right.sort_order);
  const displayMembers = buildGroupDisplayMembers(
    items,
    channelMap,
    isAvailabilityReady,
  );
  const channelNames = [
    ...new Set(
      items
        .map(
          (item) =>
            channelMap.get(item.channel_id)?.name ||
            item.channel_name ||
            item.channel_id,
        )
        .filter(Boolean),
    ),
  ];
  return {
    ...group,
    items,
    member_count: displayMembers.length,
    enabled_member_count: displayMembers.filter((member) => member.isRoutable)
      .length,
    unavailable_member_count: displayMembers.filter(
      (member) => member.isUnavailable,
    ).length,
    channel_summary: channelNames.slice(0, 2).join(" · "),
    channel_names: channelNames,
    display_members: displayMembers,
    is_route_group: false,
  };
}

/** Derive display rows for execution groups and route groups. */
export function buildGroupRows(
  groups: ModelGroup[],
  channelMap: Map<string, ProtocolMeta>,
  isAvailabilityReady: boolean,
) {
  const executionRowsById = new Map<string, GroupRow>();
  for (const group of groups) {
    if (!group.route_group_id?.trim()) {
      const row = buildExecutionRow(group, channelMap, isAvailabilityReady);
      executionRowsById.set(group.id, row);
    }
  }
  return groups.map((group) => {
    const routeGroupId = group.route_group_id?.trim() ?? "";
    if (!routeGroupId) return executionRowsById.get(group.id)!;
    const items = group.items
      .slice()
      .sort((left, right) => left.sort_order - right.sort_order);
    const targetRow = executionRowsById.get(routeGroupId);
    const channelNames = [group.route_group_name || routeGroupId || ""];
    return {
      ...group,
      items,
      member_count: 1,
      enabled_member_count: targetRow?.enabled_member_count ?? 0,
      unavailable_member_count:
        targetRow?.unavailable_member_count ?? (isAvailabilityReady ? 1 : 0),
      channel_summary: channelNames.slice(0, 2).join(" · "),
      channel_names: channelNames,
      display_members: [],
      is_route_group: true,
    };
  });
}

/** Group candidate models by their site or protocol configuration. */
export function groupModelCandidates(
  candidates: ModelGroupCandidateItem[],
  channelMap: Map<string, ProtocolMeta>,
  locale: "zh-CN" | "en-US",
) {
  const candidatesBySite = new Map<string, CandidateChannelGroup>();
  for (const candidate of candidates) {
    const channel = channelMap.get(candidate.channel_id);
    const groupKey =
      candidate.protocol_config_id ||
      channel?.site_id ||
      candidate.site_id ||
      candidate.channel_id;
    let group = candidatesBySite.get(groupKey);
    if (!group) {
      group = {
        key: groupKey,
        site_id: channel?.site_id || candidate.site_id,
        channel_name: channel?.name || candidate.channel_name,
        candidates: [],
      };
      candidatesBySite.set(groupKey, group);
    }
    group.candidates.push(candidate);
  }
  return Array.from(candidatesBySite.values()).sort((left, right) =>
    left.channel_name.localeCompare(right.channel_name, locale),
  );
}

/** Fold protocol-specific form items into editable model members. */
export function foldGroupMembers(
  formItems: FormItem[],
  protocols: ProtocolKind[],
) {
  const memberOrder = new Map<string, number>();
  const membersByKey = new Map<string, FoldedMember>();
  for (const item of formItems) {
    const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
    const key = modelFoldKey(
      protocolConfigId,
      item.credential_id,
      item.model_name,
    );
    if (!membersByKey.has(key)) {
      memberOrder.set(key, memberOrder.size);
      membersByKey.set(key, {
        key,
        protocolConfigId,
        model_name: item.model_name,
        credential_id: item.credential_id,
        credential_name: item.credential_name,
        credential_number: item.credential_number,
        protocols: [],
        subItems: [],
        enabled: false,
        invalid: false,
      });
    }
    const member = membersByKey.get(key)!;
    member.subItems.push(item);
    if (item.enabled) member.enabled = true;
    if (item.protocol && !member.protocols.includes(item.protocol)) {
      member.protocols.push(item.protocol);
    }
  }
  for (const member of membersByKey.values()) {
    member.invalid = member.subItems.every(
      (item) =>
        !item.protocol || !isItemValidForProtocols(item.protocol, protocols),
    );
  }
  return Array.from(memberOrder.entries())
    .sort((left, right) => left[1] - right[1])
    .map(([key]) => membersByKey.get(key)!);
}
