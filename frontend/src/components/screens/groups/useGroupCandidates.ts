import { type Dispatch, type SetStateAction, useEffect, useMemo } from "react";
import { useRegexRules } from "@/hooks/useRegexRules";
import type {
  ModelGroupCandidateItem,
  ModelGroupCandidatesResponse,
} from "@/lib/api/groups";
import { compileRegexRulePattern } from "@/lib/regexRules";
import type { FormState } from "./groupTypes";
import {
  applyMatchRulesToForm,
  candidatePayloadToFormItems,
  groupModelCandidates,
} from "./groupView";
import {
  buildRuleMatcher,
  modelFoldKey,
  modelGroupItemKey,
} from "./modelGroupFormatting";

type GroupCandidateOptions = {
  candidateResponse?: ModelGroupCandidatesResponse;
  /** False while the response still belongs to earlier rules or members. */
  candidateResponseIsCurrent: boolean;
  candidateSearch: string;
  expandedChannels: string[];
  form: FormState;
  isCreating: boolean;
  locale: "zh-CN" | "en-US";
  setExpandedChannels: Dispatch<SetStateAction<string[]>>;
  setForm: Dispatch<SetStateAction<FormState>>;
};

/** Derive candidate groups, preview rule members, and add sources. */
export function useGroupCandidates({
  candidateResponse,
  candidateResponseIsCurrent,
  candidateSearch,
  expandedChannels,
  form,
  isCreating,
  locale,
  setExpandedChannels,
  setForm,
}: GroupCandidateOptions) {
  const candidates = candidateResponse?.candidates;
  const regexRules = useRegexRules();
  const libraryRules = regexRules.rules;
  const invalidMatchRules = libraryRules.filter(
    (rule) =>
      form.match_rule_ids.includes(rule.id) &&
      !compileRegexRulePattern(rule.pattern),
  );
  const hasDeletedMatchRules =
    regexRules.isLoaded &&
    form.match_rule_ids.some(
      (id) => !libraryRules.some((rule) => rule.id === id),
    );
  // The backend evaluates the draft rules the same way saving and reconcile
  // do, so the preview never relies on browser regex semantics.
  const matchedModelNames = candidateResponse?.matched_model_names;
  const isRuleMatched = useMemo(
    () => buildRuleMatcher(form.match_models, matchedModelNames ?? []),
    [form.match_models, matchedModelNames],
  );
  // Members the rules cover, whatever their source; candidates only list
  // models outside the group.
  const ruleMatches = useMemo(
    () => form.items.filter((item) => isRuleMatched(item.model_name)),
    [form.items, isRuleMatched],
  );

  // A response for the current rules may add or drop rule members. Stale
  // placeholder data is skipped so an earlier rule set cannot drop them.
  useEffect(() => {
    if (!candidateResponse || !candidateResponseIsCurrent) return;
    setForm((current) =>
      applyMatchRulesToForm(
        current,
        candidateResponse.candidates,
        candidateResponse.matched_model_names,
      ),
    );
  }, [candidateResponse, candidateResponseIsCurrent, setForm]);

  // Rule edits change the candidate query, whose response re-previews members.
  function changeMatchRules(
    rules: Partial<Pick<FormState, "match_models" | "match_rule_ids">>,
  ) {
    setForm((current) => ({ ...current, ...rules }));
  }

  /** While creating, the default match rule follows the group name. */
  function changeName(name: string) {
    setForm((current) => {
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
    setForm((current) => ({
      ...current,
      route_group_id: routeGroupId,
      match_models: routeGroupId ? [] : current.match_models,
      match_rule_ids: routeGroupId ? [] : current.match_rule_ids,
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

  /** Whether saving would add this model back: a rule or the group's own name. */
  function isAutoJoined(current: FormState, modelName: string) {
    return (
      modelName.toLowerCase() === current.name.trim().toLowerCase() ||
      buildRuleMatcher(current.match_models, matchedModelNames ?? [])(modelName)
    );
  }

  return {
    addCandidate,
    changeMatchRules,
    changeName,
    changeRouteTarget,
    expandedChannels: visibleExpandedChannels,
    groupedCandidates,
    hasDeletedMatchRules,
    invalidMatchRules,
    isAutoJoined,
    ruleMatchModelCount: new Set(ruleMatches.map((item) => item.model_name))
      .size,
    ruleMatchSourceCount: new Set(
      ruleMatches.map((item) =>
        modelFoldKey(
          item.protocol_config_id,
          item.credential_id,
          item.model_name,
        ),
      ),
    ).size,
    toggleChannel,
  };
}
