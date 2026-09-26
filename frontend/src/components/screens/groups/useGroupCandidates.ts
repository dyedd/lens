import { type Dispatch, type SetStateAction, useEffect, useMemo } from "react";
import type {
  ModelGroupCandidateItem,
  ModelGroupCandidatesResponse,
} from "@/lib/api/groups";
import type { FormState } from "./groupTypes";
import {
  applyMatchRulesToForm,
  candidatePayloadToFormItems,
  groupModelCandidates,
} from "./groupView";
import {
  compileMatchRegex,
  matchesGroupRules,
  modelGroupItemKey,
} from "./modelGroupFormatting";

type GroupCandidateOptions = {
  candidateResponse?: ModelGroupCandidatesResponse;
  candidateSearch: string;
  expandedChannels: string[];
  form: FormState;
  isCreating: boolean;
  locale: "zh-CN" | "en-US";
  setExpandedChannels: Dispatch<SetStateAction<string[]>>;
  setForm: Dispatch<SetStateAction<FormState>>;
};

/** Derive candidate groups, keep live rule members current, and add sources. */
export function useGroupCandidates({
  candidateResponse,
  candidateSearch,
  expandedChannels,
  form,
  isCreating,
  locale,
  setExpandedChannels,
  setForm,
}: GroupCandidateOptions) {
  const candidates = candidateResponse?.candidates;
  const matchRegexInvalid =
    Boolean(form.match_regex.trim()) && !compileMatchRegex(form.match_regex);
  const ruleMatches = useMemo(() => {
    const regex = compileMatchRegex(form.match_regex);
    return (candidates ?? []).filter((candidate) =>
      matchesGroupRules(candidate.model_name, form.match_models, regex),
    );
  }, [candidates, form.match_models, form.match_regex]);

  // Refreshed candidates may add or drop rule members.
  useEffect(() => {
    if (!candidates) return;
    setForm((current) => applyMatchRulesToForm(current, candidates));
  }, [candidates, setForm]);

  /** Update the form and immediately re-resolve live rule members. */
  function updateRuleForm(update: (current: FormState) => FormState) {
    setForm((current) => {
      const next = update(current);
      return candidates ? applyMatchRulesToForm(next, candidates) : next;
    });
  }

  function changeMatchRules(
    rules: Partial<Pick<FormState, "match_models" | "match_regex">>,
  ) {
    updateRuleForm((current) => ({ ...current, ...rules }));
  }

  /** While creating, the default match rule follows the group name. */
  function changeName(name: string) {
    updateRuleForm((current) => {
      const currentName = current.name.trim();
      const followsName =
        isCreating &&
        !current.route_group_id &&
        current.match_models.join("\n") === currentName;
      const nextName = name.trim();
      return {
        ...current,
        name,
        match_models: followsName
          ? nextName
            ? [nextName]
            : []
          : current.match_models,
      };
    });
  }

  function changeRouteTarget(routeGroupId: string) {
    updateRuleForm((current) => ({
      ...current,
      route_group_id: routeGroupId,
      match_models: routeGroupId ? [] : current.match_models,
      match_regex: routeGroupId ? "" : current.match_regex,
      fallback_group_ids: routeGroupId ? [] : current.fallback_group_ids,
    }));
    setExpandedChannels([]);
  }

  const filteredCandidates = useMemo(() => {
    const keyword = candidateSearch.trim().toLowerCase();
    return (candidates ?? []).filter((candidate) =>
      candidate.model_name.toLowerCase().includes(keyword),
    );
  }, [candidates, candidateSearch]);
  const groupedCandidates = useMemo(
    () => groupModelCandidates(filteredCandidates, locale),
    [filteredCandidates, locale],
  );
  const availableGroupKeys = new Set(
    groupedCandidates.map((candidateGroup) => candidateGroup.key),
  );
  const closedMarker = `__closed__:${groupedCandidates
    .map((candidateGroup) => candidateGroup.key)
    .join("\u0000")}`;
  const availableExpandedChannels = expandedChannels.filter((key) =>
    availableGroupKeys.has(key),
  );
  const visibleExpandedChannels = availableExpandedChannels.length
    ? availableExpandedChannels
    : expandedChannels.includes(closedMarker)
      ? []
      : groupedCandidates.length
        ? [groupedCandidates[0].key]
        : [];

  function toggleChannel(channelId: string) {
    setExpandedChannels((current) => {
      const availableExpanded = current.filter((key) =>
        availableGroupKeys.has(key),
      );
      const visibleExpanded = availableExpanded.length
        ? availableExpanded
        : current.includes(closedMarker)
          ? []
          : groupedCandidates.length
            ? [groupedCandidates[0].key]
            : [];
      if (!visibleExpanded.includes(channelId)) {
        return [...visibleExpanded, channelId];
      }
      const nextExpanded = visibleExpanded.filter((key) => key !== channelId);
      return nextExpanded.length ? nextExpanded : [closedMarker];
    });
  }

  function addCandidate(candidate: ModelGroupCandidateItem) {
    const newFormItems = candidatePayloadToFormItems(candidate);
    setForm((current) => {
      const existingKeys = new Set(
        current.items.map((item) => modelGroupItemKey(item)),
      );
      const itemsToAdd = newFormItems.filter(
        (item) => !existingKeys.has(modelGroupItemKey(item)),
      );
      return itemsToAdd.length
        ? { ...current, items: [...current.items, ...itemsToAdd] }
        : current;
    });
  }

  return {
    addCandidate,
    changeMatchRules,
    changeName,
    changeRouteTarget,
    expandedChannels: visibleExpandedChannels,
    groupedCandidates,
    matchRegexInvalid,
    ruleMatchModelCount: new Set(
      ruleMatches.map((candidate) => candidate.model_name),
    ).size,
    ruleMatchSourceCount: ruleMatches.length,
    toggleChannel,
  };
}
