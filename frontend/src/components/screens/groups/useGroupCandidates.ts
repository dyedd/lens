import { useQuery } from "@tanstack/react-query";
import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useMemo,
  useState,
} from "react";
import { apiRequest } from "@/lib/api/client";
import type {
  ModelGroupCandidateItem,
  ModelGroupCandidatesPayload,
  ModelGroupCandidatesResponse,
} from "@/lib/api/groups";
import type { FormState } from "./groupTypes";
import { candidatePayloadToFormItems, groupModelCandidates } from "./groupView";
import { modelFoldKey, modelGroupItemKey } from "./modelGroupFormatting";
import { compileRegexRulePattern } from "./modelGroupMatching";

type GroupCandidateOptions = {
  dialogOpen: boolean;
  editingId: string | null;
  form: FormState;
  locale: "zh-CN" | "en-US";
  setForm: Dispatch<SetStateAction<FormState>>;
};

export function useGroupCandidates({
  dialogOpen,
  editingId,
  form,
  locale,
  setForm,
}: GroupCandidateOptions) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const [candidateSearch, setCandidateSearch] = useState("");
  const [candidateRegex, setCandidateRegex] = useState(false);
  const [expandedChannels, setExpandedChannels] = useState<string[]>([]);

  useEffect(() => {
    if (!dialogOpen) {
      setSheetOpen(false);
      setCandidateSearch("");
    }
    setExpandedChannels([]);
  }, [dialogOpen]);

  useEffect(() => {
    if (form.route_group_id) setExpandedChannels([]);
  }, [form.route_group_id]);

  const payload: ModelGroupCandidatesPayload = useMemo(
    () => ({
      items: form.items
        .map((item) => ({
          channel_id: item.channel_id,
          credential_id: item.credential_id,
          model_name: item.model_name,
          enabled: item.enabled,
        }))
        .sort((left, right) =>
          modelGroupItemKey(left).localeCompare(modelGroupItemKey(right)),
        ),
    }),
    [form.items],
  );
  const { data, error, isError, isFetching, refetch } = useQuery({
    queryKey: ["group-candidates", editingId, payload],
    queryFn: () =>
      apiRequest<ModelGroupCandidatesResponse>(
        "/admin/model-group-candidates",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      ),
    enabled: dialogOpen && !form.route_group_id,
    // Keep the list visible while edits to the same group are re-evaluated.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === editingId ? previous : undefined,
  });
  const candidates = data?.candidates;

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
  function resolveExpandedChannels(keys: string[]) {
    const available = keys.filter((key) => availableGroupKeys.has(key));
    if (available.length) return available;
    if (keys.includes(closedMarker)) return [];
    return groupedCandidates.length ? [groupedCandidates[0].key] : [];
  }

  const visibleExpandedChannels = resolveExpandedChannels(expandedChannels);

  function toggleChannel(channelId: string) {
    setExpandedChannels((current) => {
      const visibleExpanded = resolveExpandedChannels(current);
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
        itemsToAdd.map(
          (item) => `${modelFoldKey(item)}::${item.credential_id}`,
        ),
      );
      return itemsToAdd.length
        ? {
            ...current,
            items: [...current.items, ...itemsToAdd],
            excluded_items: current.excluded_items.filter(
              (item) =>
                !addedKeys.has(`${modelFoldKey(item)}::${item.credential_id}`),
            ),
          }
        : current;
    });
  }

  /** Adds every candidate the current search or regex shows. */
  function addAllVisibleCandidates() {
    for (const candidate of filteredCandidates) addCandidate(candidate);
  }

  return {
    addAllVisibleCandidates,
    addCandidate,
    candidateRegex,
    candidateSearch,
    error,
    evaluatedItems: data?.evaluated_items ?? [],
    expandedChannels: visibleExpandedChannels,
    existingItemKeys: new Set(form.items.map(modelGroupItemKey)),
    groupedCandidates,
    isError,
    isFetching,
    refetch,
    setCandidateRegex,
    setCandidateSearch,
    setSheetOpen,
    sheetOpen,
    toggleChannel,
    visibleCandidateCount: new Set(filteredCandidates.map(modelFoldKey)).size,
  };
}

export type GroupCandidates = ReturnType<typeof useGroupCandidates>;
