import { type Dispatch, type SetStateAction, useMemo } from "react";
import type {
  ModelGroupCandidateItem,
  ModelGroupCandidatesResponse,
} from "@/lib/api/groups";
import type { CandidateSearchMode, FormState } from "./groupTypes";
import { candidatePayloadToFormItems, groupModelCandidates } from "./groupView";
import {
  compileCandidateRegex,
  matchesCandidateSearch,
  modelGroupItemKey,
} from "./modelGroupFormatting";

type GroupCandidateOptions = {
  candidateResponse?: ModelGroupCandidatesResponse;
  candidateSearch: string;
  candidateSearchMode: CandidateSearchMode;
  expandedChannels: string[];
  locale: "zh-CN" | "en-US";
  setExpandedChannels: Dispatch<SetStateAction<string[]>>;
  setForm: Dispatch<SetStateAction<FormState>>;
};

/** Derive candidate groups and manage candidate selection actions. */
export function useGroupCandidates({
  candidateResponse,
  candidateSearch,
  candidateSearchMode,
  expandedChannels,
  locale,
  setExpandedChannels,
  setForm,
}: GroupCandidateOptions) {
  const candidateRegexInvalid =
    candidateSearchMode === "regex" &&
    Boolean(candidateSearch.trim()) &&
    !compileCandidateRegex(candidateSearch);
  const filteredCandidates = useMemo(
    () =>
      (candidateResponse?.candidates ?? []).filter((candidate) =>
        matchesCandidateSearch(
          candidate,
          candidateSearchMode,
          candidateSearch,
          locale,
        ),
      ),
    [candidateResponse, candidateSearch, candidateSearchMode, locale],
  );
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

  /** Saves the search as a live rule, or adds every candidate without one. */
  function addMatchedItems() {
    if (!filteredCandidates.length && !candidateSearch.trim()) return;
    const query = candidateSearch.trim();
    setForm((current) => {
      const existingKeys = new Set(
        current.items.map((item) => modelGroupItemKey(item)),
      );
      const additions = filteredCandidates.flatMap((candidate) =>
        candidatePayloadToFormItems(candidate, Boolean(query)).filter(
          (item) => !existingKeys.has(modelGroupItemKey(item)),
        ),
      );
      return {
        ...current,
        sync_filter_mode: query ? candidateSearchMode : "",
        sync_filter_query: query,
        items: [
          ...current.items.filter(
            (item) => !query || !item.matched_by_rule || !item.enabled,
          ),
          ...additions,
        ],
      };
    });
  }

  function clearSavedFilter() {
    setForm((current) => ({
      ...current,
      sync_filter_mode: "",
      sync_filter_query: "",
      items: current.items.filter(
        (item) => !item.matched_by_rule || !item.enabled,
      ),
    }));
  }

  return {
    addCandidate,
    addMatchedItems,
    candidateRegexInvalid,
    clearSavedFilter,
    filteredCandidates,
    groupedCandidates,
    expandedChannels: visibleExpandedChannels,
    toggleChannel,
  };
}
