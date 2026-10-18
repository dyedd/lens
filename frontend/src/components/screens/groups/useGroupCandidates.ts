import { type Dispatch, type SetStateAction, useMemo, useState } from "react";
import { useRegexRules } from "@/hooks/useRegexRules";
import type {
  ModelGroupCandidateItem,
  ModelGroupCandidatesResponse,
} from "@/lib/api/groups";
import { compileRegexRulePattern } from "@/lib/regexRules";
import type { FormState } from "./groupTypes";
import { candidatePayloadToFormItems, groupModelCandidates } from "./groupView";
import { modelGroupItemKey } from "./modelGroupFormatting";

type GroupCandidateOptions = {
  candidateResponse?: ModelGroupCandidatesResponse;
  candidateSearch: string;
  expandedChannels: string[];
  /** Rule ids the group joins by; empty means join by name. */
  joinRuleIds: string[];
  locale: "zh-CN" | "en-US";
  setExpandedChannels: Dispatch<SetStateAction<string[]>>;
  setForm: Dispatch<SetStateAction<FormState>>;
};

/** Derive candidate groups and add the sources an admin picks. */
export function useGroupCandidates({
  candidateResponse,
  candidateSearch,
  expandedChannels,
  joinRuleIds,
  locale,
  setExpandedChannels,
  setForm,
}: GroupCandidateOptions) {
  const [candidateRegex, setCandidateRegex] = useState(false);
  const library = useRegexRules();
  /** The group's rules compiled; empty keeps name matching. */
  const joinPatterns = useMemo(() => {
    const rulesById = new Map(library.rules.map((rule) => [rule.id, rule]));
    return joinRuleIds.flatMap((ruleId) => {
      const rule = rulesById.get(ruleId);
      const pattern = rule ? compileRegexRulePattern(rule.pattern) : null;
      return pattern ? [pattern] : [];
    });
  }, [joinRuleIds, library.rules]);
  const candidates = candidateResponse?.candidates;
  function changeName(name: string) {
    setForm((current) => ({ ...current, name }));
  }

  function changeRouteTarget(routeGroupId: string) {
    setForm((current) => ({
      ...current,
      route_group_id: routeGroupId,
      fallback_group_ids: routeGroupId ? [] : current.fallback_group_ids,
    }));
    setExpandedChannels([]);
  }

  const filteredCandidates = useMemo(() => {
    const keyword = candidateSearch.trim();
    const pattern =
      candidateRegex && keyword ? compileRegexRulePattern(keyword) : null;
    const lowered = keyword.toLowerCase();
    return (candidates ?? []).filter((candidate) =>
      pattern
        ? pattern.test(candidate.model_name)
        : candidate.model_name.toLowerCase().includes(lowered),
    );
  }, [candidateRegex, candidates, candidateSearch]);
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

  /** Adding a member by hand also lifts its exclusion. */
  function addCandidate(candidate: ModelGroupCandidateItem) {
    const newFormItems = candidatePayloadToFormItems(candidate);
    setForm((current) => {
      const existingKeys = new Set(
        current.items.map((item) => modelGroupItemKey(item)),
      );
      const itemsToAdd = newFormItems.filter(
        (item) => !existingKeys.has(modelGroupItemKey(item)),
      );
      const addedKeys = new Set(
        itemsToAdd.map((item) => modelGroupItemKey(item)),
      );
      return itemsToAdd.length
        ? {
            ...current,
            items: [...current.items, ...itemsToAdd],
            excluded_items: current.excluded_items.filter(
              (item) => !addedKeys.has(modelGroupItemKey(item)),
            ),
          }
        : current;
    });
  }

  /** Adds every candidate the current search or regex shows. */
  function addAllVisibleCandidates() {
    for (const candidate of filteredCandidates) addCandidate(candidate);
  }

  /** Whether saving would join this model back by the group's rules or name. */
  function isAutoJoined(current: FormState, modelName: string) {
    if (joinPatterns.length) {
      return joinPatterns.some((joinPattern) => joinPattern.test(modelName));
    }
    const name = current.name.trim();
    return name !== "" && modelName.trim().toLowerCase() === name.toLowerCase();
  }

  return {
    addAllVisibleCandidates,
    addCandidate,
    candidateRegex,
    changeName,
    changeRouteTarget,
    expandedChannels: visibleExpandedChannels,
    groupedCandidates,
    isAutoJoined,
    setCandidateRegex,
    visibleCandidateCount: filteredCandidates.length,
    toggleChannel,
  };
}
