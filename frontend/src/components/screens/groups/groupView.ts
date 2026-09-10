import type { ModelGroup, ModelGroupCandidateItem } from "@/lib/api/groups";
import {
  headerDraftToRules,
  headerRulesToDraft,
  paramOverrideDraftToRules,
  paramOverrideRulesToDraft,
} from "@/lib/upstreamRules";
import type { FormItem, FormState } from "./groupTypes";

/** Convert candidate payload items into editable model group members. */
export function candidatePayloadToFormItems(
  candidate: ModelGroupCandidateItem,
): FormItem[] {
  return candidate.items.map((payloadItem) => ({
    channel_id: payloadItem.channel_id,
    site_id: candidate.site_id,
    protocol_config_id: payloadItem.protocol_config_id,
    channel_name: candidate.channel_name,
    protocol: payloadItem.protocol,
    credential_id: payloadItem.credential_id,
    credential_name: candidate.credential_name,
    credential_number: candidate.credential_number,
    rate_multiplier: candidate.rate_multiplier,
    rate_source: candidate.rate_source,
    model_name: payloadItem.model_name,
    enabled: true,
    state: null,
    reasons: [],
  }));
}

/** Convert a persisted model group into editor form state. */
export function modelGroupToForm(group: ModelGroup): FormState {
  return {
    name: group.name,
    strategy: group.strategy,
    route_group_id: group.route_group_id ?? "",
    sync_filter_mode: group.sync_filter_mode,
    sync_filter_query: group.sync_filter_query,
    param_override: paramOverrideRulesToDraft(group.param_override),
    headers: headerRulesToDraft(group.headers),
    fallback_group_ids: group.fallback_group_ids ?? [],
    input_price_per_million: String(group.input_price_per_million),
    output_price_per_million: String(group.output_price_per_million),
    cache_read_price_per_million: String(group.cache_read_price_per_million),
    cache_write_price_per_million: String(group.cache_write_price_per_million),
    image_price_per_image: String(group.image_price_per_image),
    pricing_mode: group.pricing_mode,
    items: group.items
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((item) => ({
        channel_id: item.channel_id,
        site_id: item.site_id,
        protocol_config_id: item.protocol_config_id,
        channel_name: item.channel_name,
        protocol: item.protocol,
        credential_id: item.credential_id,
        credential_name: item.credential_name,
        credential_number: item.credential_number,
        rate_multiplier: item.rate_multiplier,
        rate_source: item.rate_source,
        model_name: item.model_name,
        enabled: item.enabled,
        state: item.state,
        reasons: item.reasons,
      })),
  };
}

/** Convert editor form state into a model-group API payload. */
export function formToModelGroupPayload(form: FormState) {
  return {
    name: form.name.trim(),
    strategy: form.strategy,
    route_group_id: form.route_group_id.trim(),
    sync_filter_mode:
      form.route_group_id.trim() || !form.sync_filter_query.trim()
        ? ""
        : form.sync_filter_mode,
    sync_filter_query: form.route_group_id.trim()
      ? ""
      : form.sync_filter_query.trim(),
    param_override: paramOverrideDraftToRules(form.param_override),
    headers: headerDraftToRules(form.headers),
    fallback_group_ids: form.fallback_group_ids,
    items: form.items.map((item) => ({
      channel_id: item.channel_id,
      credential_id: item.credential_id,
      model_name: item.model_name,
      enabled: item.enabled,
    })),
  };
}

import type {
  CandidateChannelGroup,
  ChannelMemberGroup,
  EvaluatedFormItem,
  FoldedMember,
  GroupRow,
} from "./groupTypes";
import {
  buildGroupDisplayChannels,
  buildGroupDisplayMembers,
  modelFoldKey,
  modelGroupChannelKey,
  modelGroupItemKey,
} from "./modelGroupFormatting";

function buildExecutionRow(group: ModelGroup): GroupRow {
  const items = group.items
    .slice()
    .sort((left, right) => left.sort_order - right.sort_order);
  const displayMembers = buildGroupDisplayMembers(items);
  const displayChannels = buildGroupDisplayChannels(displayMembers);
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
      (member) => member.ready_item_count > 0,
    ).length,
    problem_member_count: displayMembers.filter(
      (member) =>
        member.invalid_item_count > 0 || member.unavailable_item_count > 0,
    ).length,
    channel_summary: channelNames.slice(0, 2).join(" · "),
    channel_names: channelNames,
    display_members: displayMembers,
    display_channels: displayChannels,
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
      display_channels: [],
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
    evaluatedItems.map((item) => [modelGroupItemKey(item), item]),
  );
  const membersByKey = new Map<string, FoldedMember>();

  for (const item of formItems) {
    const evaluation = evaluatedItemsByKey.get(modelGroupItemKey(item));
    const evaluationMatchesForm = evaluation?.enabled === item.enabled;
    const evaluatedItem: EvaluatedFormItem = {
      ...item,
      site_id: evaluation ? evaluation.site_id : item.site_id,
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
      rate_multiplier: evaluation
        ? evaluation.rate_multiplier
        : item.rate_multiplier,
      rate_source: evaluation ? evaluation.rate_source : item.rate_source,
      state:
        evaluation && evaluationMatchesForm ? evaluation.state : item.state,
      reasons:
        evaluation && evaluationMatchesForm ? evaluation.reasons : item.reasons,
    };
    const key = modelFoldKey(
      evaluatedItem.protocol_config_id,
      evaluatedItem.credential_id,
      evaluatedItem.model_name,
    );
    if (!membersByKey.has(key)) {
      membersByKey.set(key, {
        key,
        protocolConfigId: evaluatedItem.protocol_config_id,
        siteId: evaluatedItem.site_id,
        channel_id: evaluatedItem.channel_id,
        channel_name: evaluatedItem.channel_name,
        model_name: evaluatedItem.model_name,
        credential_id: evaluatedItem.credential_id,
        credential_name: evaluatedItem.credential_name,
        credential_number: evaluatedItem.credential_number,
        rate_multiplier: evaluatedItem.rate_multiplier,
        rate_source: evaluatedItem.rate_source,
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

  return Array.from(membersByKey.values());
}

/** Group visible members by site without changing their route indexes. */
export function groupFoldedMembersByChannel(
  visibleMembers: Array<{ member: FoldedMember; index: number }>,
): ChannelMemberGroup[] {
  const groupsByKey = new Map<string, Omit<ChannelMemberGroup, "priority">>();

  for (const entry of visibleMembers) {
    const { member } = entry;
    const key = modelGroupChannelKey(member.siteId, member.channel_id);
    let group = groupsByKey.get(key);
    if (!group) {
      group = {
        key,
        channel_id: member.channel_id,
        channel_name: member.channel_name,
        members: [],
      };
      groupsByKey.set(key, group);
    }
    group.members.push(entry);
  }

  const groups = Array.from(groupsByKey.values());
  return groups.map((group, index) => ({
    ...group,
    priority: index + 1,
  }));
}
