import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupItemPayload,
} from "@/lib/api/groups";
import {
  formatContextWindow,
  parseContextWindowInput,
} from "@/lib/contextWindow";
import {
  headerDraftToRules,
  headerRulesToDraft,
  paramOverrideDraftToRules,
  paramOverrideRulesToDraft,
} from "@/lib/upstreamRules";
import type {
  CandidateChannelGroup,
  ChannelMemberGroup,
  EvaluatedFormItem,
  FoldedMember,
  FormItem,
  FormState,
  GroupRow,
  SimilarGroupView,
} from "./groupTypes";
import {
  buildGroupDisplayMembers,
  buildModelMatchKey,
  modelFoldKey,
  modelGroupChannelKey,
  modelGroupItemKey,
} from "./modelGroupFormatting";

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
    credential_mask: candidate.credential_mask,
    base_url: candidate.base_url,
    rate_multiplier: candidate.rate_multiplier,
    rate_source: candidate.rate_source,
    model_name: payloadItem.model_name,
    enabled: true,
    source: "manual",
    // Added before the next evaluation, so the row stays pending until then.
    state: null,
    reasons: [],
    context_window: null,
    context_window_source: null,
  }));
}

function modelGroupItemToFormItem(item: ModelGroup["items"][number]): FormItem {
  return {
    channel_id: item.channel_id,
    site_id: item.site_id,
    protocol_config_id: item.protocol_config_id,
    channel_name: item.channel_name,
    protocol: item.protocol,
    credential_id: item.credential_id,
    credential_name: item.credential_name,
    credential_number: item.credential_number,
    credential_mask: item.credential_mask,
    base_url: item.base_url,
    rate_multiplier: item.rate_multiplier,
    rate_source: item.rate_source,
    model_name: item.model_name,
    enabled: item.enabled,
    source: item.source,
    state: item.state,
    reasons: item.reasons,
    context_window: item.context_window,
    context_window_source: item.context_window_source,
  };
}

/** Convert a persisted model group into editor form state. */
export function modelGroupToForm(group: ModelGroup): FormState {
  return {
    name: group.name,
    strategy: group.strategy,
    route_group_id: group.route_group_id ?? "",
    match_rule_ids: group.match_rule_ids,
    param_override: paramOverrideRulesToDraft(group.param_override),
    headers: headerRulesToDraft(group.headers),
    fallback_group_ids: group.fallback_group_ids ?? [],
    context_window:
      group.context_window === null
        ? ""
        : formatContextWindow(group.context_window),
    items: group.items
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order)
      .map(modelGroupItemToFormItem),
    excluded_items: group.excluded_items.map(modelGroupItemToFormItem),
  };
}

function formItemToPayload(item: FormItem): ModelGroupItemPayload {
  return {
    channel_id: item.channel_id,
    credential_id: item.credential_id,
    model_name: item.model_name,
    enabled: item.enabled,
    source: item.source,
  };
}

/** Convert editor form state into a model-group API payload. */
export function formToModelGroupPayload(form: FormState) {
  const routeGroupId = form.route_group_id.trim();
  return {
    name: form.name.trim(),
    strategy: form.strategy,
    route_group_id: routeGroupId,
    match_rule_ids: routeGroupId ? [] : form.match_rule_ids,
    param_override: paramOverrideDraftToRules(form.param_override),
    headers: headerDraftToRules(form.headers),
    fallback_group_ids: form.fallback_group_ids,
    context_window: parseContextWindowInput(form.context_window) ?? null,
    items: form.items.map(formItemToPayload),
    excluded_items: form.excluded_items.map(formItemToPayload),
  };
}

function buildSimilarGroupsById(groups: ModelGroup[]) {
  const groupIdsByKey = new Map<string, Set<string>>();
  const keysByGroupId = new Map<string, Set<string>>();
  for (const group of groups) {
    if (group.route_group_id?.trim()) continue;
    const keys = new Set([group.name].map(buildModelMatchKey));
    keys.delete("");
    keysByGroupId.set(group.id, keys);
    for (const key of keys) {
      const ids = groupIdsByKey.get(key) ?? new Set<string>();
      ids.add(group.id);
      groupIdsByKey.set(key, ids);
    }
  }
  const namesById = new Map(groups.map((group) => [group.id, group.name]));
  const similarById = new Map<string, SimilarGroupView[]>();
  for (const [groupId, keys] of keysByGroupId) {
    const similarIds = new Set<string>();
    for (const key of keys) {
      for (const id of groupIdsByKey.get(key) ?? []) {
        if (id !== groupId) similarIds.add(id);
      }
    }
    similarById.set(
      groupId,
      [...similarIds].map((id) => ({ id, name: namesById.get(id) ?? id })),
    );
  }
  return similarById;
}

function buildExecutionRow(
  group: ModelGroup,
  similarGroups: SimilarGroupView[],
): GroupRow {
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
      (member) => member.ready_item_count > 0,
    ).length,
    problem_member_count: displayMembers.filter(
      (member) =>
        member.invalid_item_count > 0 || member.unavailable_item_count > 0,
    ).length,
    site_count: new Set(
      items.map((item) => modelGroupChannelKey(item.site_id, item.channel_id)),
    ).size,
    credential_count: new Set(items.map((item) => item.credential_id)).size,
    channel_names: channelNames,
    display_members: displayMembers,
    similar_groups: similarGroups,
    is_route_group: false,
  };
}

/** Derive display rows for execution groups and route groups. */
export function buildGroupRows(groups: ModelGroup[]): GroupRow[] {
  const similarById = buildSimilarGroupsById(groups);
  const executionRowsById = new Map<string, GroupRow>();
  for (const group of groups) {
    if (!group.route_group_id?.trim()) {
      executionRowsById.set(
        group.id,
        buildExecutionRow(group, similarById.get(group.id) ?? []),
      );
    }
  }
  return groups.map((group) => {
    const routeGroupId = group.route_group_id?.trim() ?? "";
    if (!routeGroupId) return executionRowsById.get(group.id)!;
    const items = group.items
      .slice()
      .sort((left, right) => left.sort_order - right.sort_order);
    const targetRow = executionRowsById.get(routeGroupId);
    return {
      ...group,
      items,
      member_count: 1,
      enabled_member_count: targetRow?.enabled_member_count ?? 0,
      problem_member_count: targetRow?.problem_member_count ?? 1,
      site_count: 0,
      credential_count: 0,
      channel_names: [group.route_group_name || routeGroupId],
      display_members: [],
      similar_groups: [],
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
    const evaluatedItem: EvaluatedFormItem = evaluation
      ? {
          ...item,
          site_id: evaluation.site_id,
          protocol_config_id: evaluation.protocol_config_id,
          channel_name: evaluation.channel_name,
          protocol: evaluation.protocol,
          credential_name: evaluation.credential_name,
          credential_number: evaluation.credential_number,
          credential_mask: evaluation.credential_mask,
          base_url: evaluation.base_url,
          rate_multiplier: evaluation.rate_multiplier,
          rate_source: evaluation.rate_source,
          context_window: evaluation.context_window,
          context_window_source: evaluation.context_window_source,
          state: evaluationMatchesForm ? evaluation.state : item.state,
          reasons: evaluationMatchesForm ? evaluation.reasons : item.reasons,
        }
      : item;
    const key = modelFoldKey(
      evaluatedItem.protocol_config_id,
      evaluatedItem.credential_id,
      evaluatedItem.model_name,
    );
    let member = membersByKey.get(key);
    if (!member) {
      member = {
        key,
        protocolConfigId: evaluatedItem.protocol_config_id,
        siteId: evaluatedItem.site_id,
        channel_id: evaluatedItem.channel_id,
        channel_name: evaluatedItem.channel_name,
        model_name: evaluatedItem.model_name,
        credential_id: evaluatedItem.credential_id,
        credential_name: evaluatedItem.credential_name,
        credential_number: evaluatedItem.credential_number,
        credential_mask: evaluatedItem.credential_mask,
        base_url: evaluatedItem.base_url,
        rate_multiplier: evaluatedItem.rate_multiplier,
        rate_source: evaluatedItem.rate_source,
        context_window: evaluatedItem.context_window,
        context_window_source: evaluatedItem.context_window_source,
        subItems: [],
        source: evaluatedItem.source,
        enabled_item_count: 0,
        disabled_item_count: 0,
        ready_item_count: 0,
        invalid_item_count: 0,
        unavailable_item_count: 0,
        pending_item_count: 0,
      };
      membersByKey.set(key, member);
    }
    member.subItems.push(evaluatedItem);
    if (member.source !== evaluatedItem.source) member.source = "manual";
    if (evaluatedItem.enabled) member.enabled_item_count += 1;
    else member.disabled_item_count += 1;
    if (evaluatedItem.state === null) member.pending_item_count += 1;
    if (evaluatedItem.state === "ready") member.ready_item_count += 1;
    if (evaluatedItem.state === "invalid") member.invalid_item_count += 1;
    if (evaluatedItem.state === "unavailable") {
      member.unavailable_item_count += 1;
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

  return Array.from(groupsByKey.values()).map((group, index) => ({
    ...group,
    priority: index + 1,
  }));
}
