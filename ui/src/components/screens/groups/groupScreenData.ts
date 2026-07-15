import type { ModelGroup, ModelGroupCandidateItem } from "@/lib/api";
import {
  buildGroupDisplayMembers,
  itemKey,
  modelFoldKey,
  type CandidateChannelGroup,
  type EvaluatedFormItem,
  type FoldedMember,
  type FormItem,
  type GroupRow,
} from "./modelGroupUtils";

function buildExecutionRow(group: ModelGroup): GroupRow {
  const items = group.items
    .slice()
    .sort((left, right) => left.sort_order - right.sort_order);
  const displayMembers = buildGroupDisplayMembers(items);
  const channelNames = [
    ...new Set(
      items.map((item) => item.channel_name || item.channel_id).filter(Boolean),
    ),
  ];
  return {
    ...group,
    items,
    member_count: displayMembers.length,
    enabled_member_count: displayMembers.filter(
      (member) => member.enabled_item_count > 0,
    ).length,
    problem_member_count: displayMembers.filter(
      (member) =>
        member.invalid_item_count > 0 || member.unavailable_item_count > 0,
    ).length,
    channel_summary: channelNames.slice(0, 2).join(" · "),
    channel_names: channelNames,
    display_members: displayMembers,
    is_route_group: false,
  };
}

/** Derive display rows for execution groups and route groups. */
export function buildGroupRows(groups: ModelGroup[]) {
  const executionRowsById = new Map<string, GroupRow>();
  for (const group of groups) {
    if (!group.route_group_id?.trim()) {
      const row = buildExecutionRow(group);
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
      problem_member_count: targetRow?.problem_member_count ?? 1,
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
  locale: "zh-CN" | "en-US",
) {
  const candidatesBySite = new Map<string, CandidateChannelGroup>();
  for (const candidate of candidates) {
    const groupKey = candidate.protocol_config_id;
    let group = candidatesBySite.get(groupKey);
    if (!group) {
      group = {
        key: groupKey,
        site_id: candidate.site_id,
        channel_name: candidate.channel_name,
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

/** Fold protocol-specific form items using the latest backend evaluation. */
export function foldGroupMembers(
  formItems: FormItem[],
  evaluatedItems: ModelGroup["items"],
) {
  const evaluatedItemsByKey = new Map(
    evaluatedItems.map((item) => [itemKey(item), item]),
  );
  const memberOrder = new Map<string, number>();
  const membersByKey = new Map<string, FoldedMember>();

  for (const item of formItems) {
    const evaluation = evaluatedItemsByKey.get(itemKey(item));
    const evaluatedItem: EvaluatedFormItem = {
      ...item,
      protocol_config_id: evaluation
        ? evaluation.protocol_config_id
        : item.protocol_config_id,
      channel_name: evaluation ? evaluation.channel_name : item.channel_name,
      protocol: evaluation ? evaluation.protocol : item.protocol,
      credential_name: evaluation
        ? evaluation.credential_name
        : item.credential_name,
      credential_number: evaluation
        ? evaluation.credential_number
        : item.credential_number,
      state: evaluation ? evaluation.state : item.state,
      reasons: evaluation ? evaluation.reasons : item.reasons,
    };
    const key = modelFoldKey(
      evaluatedItem.protocol_config_id,
      evaluatedItem.credential_id,
      evaluatedItem.model_name,
    );
    if (!membersByKey.has(key)) {
      memberOrder.set(key, memberOrder.size);
      membersByKey.set(key, {
        key,
        protocolConfigId: evaluatedItem.protocol_config_id,
        model_name: evaluatedItem.model_name,
        credential_id: evaluatedItem.credential_id,
        credential_name: evaluatedItem.credential_name,
        credential_number: evaluatedItem.credential_number,
        protocols: [],
        subItems: [],
        enabled_item_count: 0,
        disabled_item_count: 0,
        ready_item_count: 0,
        invalid_item_count: 0,
        unavailable_item_count: 0,
        pending_item_count: 0,
      });
    }
    const member = membersByKey.get(key)!;
    member.subItems.push(evaluatedItem);
    if (evaluatedItem.enabled) member.enabled_item_count += 1;
    else member.disabled_item_count += 1;
    if (evaluatedItem.state === null) member.pending_item_count += 1;
    if (evaluatedItem.state === "ready") member.ready_item_count += 1;
    if (evaluatedItem.state === "invalid") {
      member.invalid_item_count += 1;
    }
    if (evaluatedItem.state === "unavailable") {
      member.unavailable_item_count += 1;
    }
    if (
      evaluatedItem.protocol &&
      !member.protocols.includes(evaluatedItem.protocol)
    ) {
      member.protocols.push(evaluatedItem.protocol);
    }
  }

  return Array.from(memberOrder.entries())
    .sort((left, right) => left[1] - right[1])
    .map(([key]) => membersByKey.get(key)!);
}
