import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { apiRequest } from "@/lib/api/client";
import type {
  ModelGroup,
  ModelGroupCandidatesPayload,
  ModelGroupCandidatesResponse,
  RoutingStrategy,
} from "@/lib/api/groups";
import { getModelFamilyKey } from "@/lib/ModelIcons";
import {
  buildModelPrefixOptions,
  resolveEffectiveModelPrefix,
  type SelectedModelPrefix,
} from "@/lib/modelPrefix";
import type { FormState, GroupRow, GroupSort } from "./groupTypes";
import { buildGroupRows } from "./groupView";
import { modelGroupItemKey } from "./modelGroupFormatting";

type GroupsQueryOptions = {
  dialogOpen: boolean;
  editingId: string | null;
  form: FormState;
  locale: "zh-CN" | "en-US";
};

/** Load model group data and derive query-backed display metadata. */
export function useGroupsQueries({
  dialogOpen,
  editingId,
  form,
  locale,
}: GroupsQueryOptions) {
  const queryClient = useQueryClient();
  const groupsQuery = useQuery({
    queryKey: ["groups"],
    queryFn: () => apiRequest<ModelGroup[]>("/admin/model-groups"),
    staleTime: 2 * 60_000,
  });
  const candidatePayload: ModelGroupCandidatesPayload = useMemo(
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
  const candidateQuery = useQuery({
    queryKey: ["group-candidates", candidatePayload],
    queryFn: () =>
      apiRequest<ModelGroupCandidatesResponse>(
        "/admin/model-group-candidates",
        {
          method: "POST",
          body: JSON.stringify(candidatePayload),
        },
      ),
    enabled: dialogOpen && !form.route_group_id,
  });
  const groupRows = useMemo(
    () => buildGroupRows(groupsQuery.data ?? []),
    [groupsQuery.data],
  );
  const routeTargetOptions = useMemo(
    () =>
      (groupsQuery.data ?? [])
        .filter(
          (group) =>
            !group.route_group_id &&
            group.id !== editingId &&
            group.items.some((item) => item.enabled && item.state === "ready"),
        )
        .sort((left, right) => left.name.localeCompare(right.name, locale)),
    [editingId, groupsQuery.data, locale],
  );

  useEffect(() => {
    if (!groupsQuery.isError) return;
    toast.error(
      locale === "zh-CN" ? "模型组加载失败" : "Failed to load groups",
      {
        id: "groups-load-error",
        description:
          groupsQuery.error instanceof Error
            ? groupsQuery.error.message
            : locale === "zh-CN"
              ? "无法读取模型组"
              : "Unable to read groups",
      },
    );
  }, [groupsQuery.error, groupsQuery.isError, locale]);

  async function invalidateGroupData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["groups"] }),
      queryClient.invalidateQueries({ queryKey: ["group-candidates"] }),
    ]);
  }

  return {
    candidateQuery,
    evaluatedItems: candidateQuery.data?.evaluated_items ?? [],
    groupRows,
    groups: groupsQuery.data,
    groupsIsError: groupsQuery.isError,
    invalidateGroupData,
    isLoading: groupsQuery.isLoading,
    queryClient,
    routeTargetOptions,
  };
}

/** Manage model group filters and derive the visible sorted rows. */
export function useGroupFilters(
  groupRows: GroupRow[],
  locale: "zh-CN" | "en-US",
) {
  const [selectedModelPrefix, setSelectedModelPrefix] =
    useState<SelectedModelPrefix>("all");
  const [search, setSearch] = useState("");
  const [strategyFilter, setStrategyFilter] = useState<"all" | RoutingStrategy>(
    "all",
  );
  const [sortBy, setSortBy] = useState<GroupSort>("members-desc");
  const modelPrefixOptions = useMemo(
    () =>
      buildModelPrefixOptions(
        groupRows.map((group) => group.name),
        locale,
      ),
    [groupRows, locale],
  );
  const effectiveSelectedModelPrefix = resolveEffectiveModelPrefix(
    modelPrefixOptions,
    selectedModelPrefix,
  );
  const visibleGroups = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    const filtered = groupRows.filter((group) => {
      if (
        effectiveSelectedModelPrefix !== "all" &&
        getModelFamilyKey(group.name) !== effectiveSelectedModelPrefix
      ) {
        return false;
      }
      if (strategyFilter !== "all" && group.strategy !== strategyFilter) {
        return false;
      }
      if (!keyword) return true;
      return [
        group.name,
        group.channel_summary,
        ...group.channel_names,
        ...group.items.map((item) => item.model_name),
      ]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    });
    return [...filtered].sort((left, right) => {
      if (sortBy === "name-asc") {
        return left.name.localeCompare(right.name, locale);
      }
      if (sortBy === "name-desc") {
        return right.name.localeCompare(left.name, locale);
      }
      if (sortBy === "enabled-desc") {
        return (
          right.enabled_member_count - left.enabled_member_count ||
          left.name.localeCompare(right.name, locale)
        );
      }
      return (
        right.member_count - left.member_count ||
        left.name.localeCompare(right.name, locale)
      );
    });
  }, [
    effectiveSelectedModelPrefix,
    groupRows,
    locale,
    search,
    sortBy,
    strategyFilter,
  ]);

  function resetFilters() {
    setSelectedModelPrefix("all");
    setSearch("");
    setStrategyFilter("all");
    setSortBy("members-desc");
  }

  return {
    activeFilterCount: [
      effectiveSelectedModelPrefix !== "all",
      Boolean(search.trim()),
      strategyFilter !== "all",
    ].filter(Boolean).length,
    effectiveSelectedModelPrefix,
    hasModelPrefixOptions: modelPrefixOptions.length > 0,
    modelPrefixOptions,
    resetFilters,
    search,
    setSearch,
    setSelectedModelPrefix,
    setSortBy,
    setStrategyFilter,
    sortBy,
    strategyFilter,
    visibleGroups,
  };
}
