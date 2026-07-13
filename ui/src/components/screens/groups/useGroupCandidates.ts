"use client";

import { useMemo, type Dispatch, type SetStateAction } from "react";
import { toast } from "sonner";
import {
  apiRequest,
  type ModelGroupCandidateItem,
  type ModelGroupCandidatesPayload,
  type ModelGroupCandidatesResponse,
} from "@/lib/api";
import { groupModelCandidates } from "./groupScreenData";
import {
  candidatePayloadToFormItems,
  compileCandidateRegex,
  itemKey,
  matchesCandidateSearch,
  modelGroupErrorMessage,
  type CandidateSearchMode,
  type FormItem,
  type FormState,
  type ProtocolMeta,
} from "./modelGroupUtils";

type GroupCandidateOptions = {
  candidateResponse?: ModelGroupCandidatesResponse;
  candidateSearch: string;
  candidateSearchMode: CandidateSearchMode;
  channelMap: Map<string, ProtocolMeta>;
  expandedChannels: string[];
  form: FormState;
  locale: "zh-CN" | "en-US";
  setExpandedChannels: Dispatch<SetStateAction<string[]>>;
  setForm: Dispatch<SetStateAction<FormState>>;
};

/** Derive candidate groups and manage candidate selection actions. */
export function useGroupCandidates({
  candidateResponse,
  candidateSearch,
  candidateSearchMode,
  channelMap,
  expandedChannels,
  form,
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
          channelMap,
          locale,
        ),
      ),
    [
      candidateResponse,
      candidateSearch,
      candidateSearchMode,
      channelMap,
      locale,
    ],
  );
  const groupedCandidates = useMemo(
    () => groupModelCandidates(filteredCandidates, channelMap, locale),
    [channelMap, filteredCandidates, locale],
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
    const newFormItems = candidatePayloadToFormItems(candidate, channelMap);
    setForm((current) => {
      const existingKeys = new Set(current.items.map((item) => itemKey(item)));
      const itemsToAdd = newFormItems.filter(
        (item) => !existingKeys.has(itemKey(item)),
      );
      return itemsToAdd.length
        ? { ...current, items: [...current.items, ...itemsToAdd] }
        : current;
    });
  }

  function addMatchedItems() {
    if (!filteredCandidates.length && !candidateSearch.trim()) return;
    setForm((current) => {
      const existingKeys = new Set(current.items.map((item) => itemKey(item)));
      const additions = filteredCandidates.flatMap((candidate) =>
        candidatePayloadToFormItems(candidate, channelMap).filter(
          (item) => !existingKeys.has(itemKey(item)),
        ),
      );
      return {
        ...current,
        sync_filter_mode: candidateSearch.trim() ? candidateSearchMode : "",
        sync_filter_query: candidateSearch.trim(),
        items: additions.length
          ? [...current.items, ...additions]
          : current.items,
      };
    });
  }

  async function applySavedFilter() {
    if (!form.sync_filter_mode || !form.sync_filter_query.trim()) return;
    if (
      form.sync_filter_mode === "regex" &&
      !compileCandidateRegex(form.sync_filter_query)
    ) {
      toast.error(
        locale === "zh-CN" ? "保存的正则表达式无效" : "Saved regex is invalid",
      );
      return;
    }
    try {
      const response = await apiRequest<ModelGroupCandidatesResponse>(
        "/admin/model-group-candidates",
        {
          method: "POST",
          body: JSON.stringify({
            protocols: form.protocols,
            exclude_items: [],
          } satisfies ModelGroupCandidatesPayload),
        },
      );
      const previousItems = new Map(
        form.items.map((item) => [itemKey(item), item]),
      );
      const matchedItems: FormItem[] = [];
      const matchedKeys = new Set<string>();
      for (const candidate of response.candidates) {
        if (
          !matchesCandidateSearch(
            candidate,
            form.sync_filter_mode as CandidateSearchMode,
            form.sync_filter_query,
            channelMap,
            locale,
          )
        ) {
          continue;
        }
        for (const item of candidatePayloadToFormItems(candidate, channelMap)) {
          const key = itemKey(item);
          if (matchedKeys.has(key)) continue;
          matchedKeys.add(key);
          const previousItem = previousItems.get(key);
          matchedItems.push(
            previousItem ? { ...item, enabled: previousItem.enabled } : item,
          );
        }
      }
      const existingKeys = new Set(
        form.items
          .map((item) => itemKey(item))
          .filter((key) => matchedKeys.has(key)),
      );
      const nextItems = [
        ...matchedItems.filter((item) => existingKeys.has(itemKey(item))),
        ...matchedItems.filter((item) => !existingKeys.has(itemKey(item))),
      ];
      setForm((current) => ({ ...current, items: nextItems }));
      toast.success(
        locale === "zh-CN"
          ? `已按规则更新 ${nextItems.length} 个模型，保存后生效`
          : `Updated ${nextItems.length} models by rule. Save to apply`,
      );
    } catch (error) {
      toast.error(
        modelGroupErrorMessage(
          error,
          locale === "zh-CN" ? "按规则更新失败" : "Failed to update by rule",
        ),
      );
    }
  }

  function clearSavedFilter() {
    setForm((current) => ({
      ...current,
      sync_filter_mode: "",
      sync_filter_query: "",
    }));
  }

  return {
    addCandidate,
    addMatchedItems,
    applySavedFilter,
    candidateRegexInvalid,
    clearSavedFilter,
    filteredCandidates,
    groupedCandidates,
    expandedChannels: visibleExpandedChannels,
    toggleChannel,
  };
}
