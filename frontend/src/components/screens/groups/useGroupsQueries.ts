import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useModelGroupsQuery } from "@/hooks/useModelGroupsQuery";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { RoutingStrategy, UnplacedModelsResponse } from "@/lib/api/groups";
import { getModelFamilyKey } from "@/lib/ModelIcons";
import {
  buildModelPrefixOptions,
  resolveEffectiveModelPrefix,
  type SelectedModelPrefix,
} from "@/lib/modelPrefix";
import type { GroupRow, GroupSort } from "./groupTypes";
import { buildGroupRows } from "./groupView";

type GroupsQueryOptions = {
  editingId: string | null;
  locale: "zh-CN" | "en-US";
};

/** Load model group data and derive query-backed display metadata. */
export function useGroupsQueries({ editingId, locale }: GroupsQueryOptions) {
  const queryClient = useQueryClient();
  const groupsQuery = useModelGroupsQuery();
  // Nested under "groups" so every groups invalidation refreshes it too.
  const unplacedQuery = useQuery({
    queryKey: ["groups", "unplaced-models"],
    queryFn: () => apiRequest<UnplacedModelsResponse>("/admin/unplaced-models"),
    staleTime: 2 * 60_000,
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
        description: getApiErrorMessage(
          groupsQuery.error,
          locale === "zh-CN" ? "无法读取模型组" : "Unable to read groups",
        ),
      },
    );
  }, [groupsQuery.error, groupsQuery.isError, locale]);

  useEffect(() => {
    if (!unplacedQuery.isError) return;
    toast.error(
      getApiErrorMessage(
        unplacedQuery.error,
        locale === "zh-CN"
          ? "未分配模型加载失败"
          : "Failed to load unplaced models",
      ),
      { id: "unplaced-models-load-error" },
    );
  }, [unplacedQuery.error, unplacedQuery.isError, locale]);

  async function invalidateGroupData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["groups"] }),
      queryClient.invalidateQueries({ queryKey: ["group-candidates"] }),
    ]);
  }

  return {
    groupRows,
    groups: groupsQuery.data,
    unplacedModels: unplacedQuery.data?.items ?? [],
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
  const [familyFilter, setFamilyFilter] = useState<SelectedModelPrefix>("all");
  const [search, setSearch] = useState("");
  const [strategyFilter, setStrategyFilter] = useState<"all" | RoutingStrategy>(
    "all",
  );
  const [sortBy, setSortBy] = useState<GroupSort>("members-desc");
  const familyOptions = useMemo(
    () =>
      buildModelPrefixOptions(
        groupRows.map((group) => group.name),
        locale,
      ).filter((option) => option.key !== "all"),
    [groupRows, locale],
  );
  const effectiveFamilyFilter = resolveEffectiveModelPrefix(
    familyOptions,
    familyFilter,
  );
  const visibleGroups = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    const filtered = groupRows.filter((group) => {
      if (
        effectiveFamilyFilter !== "all" &&
        getModelFamilyKey(group.name) !== effectiveFamilyFilter
      ) {
        return false;
      }
      if (strategyFilter !== "all" && group.strategy !== strategyFilter) {
        return false;
      }
      if (!keyword) return true;
      return [
        group.name,
        ...group.channel_names,
        ...group.items.map((item) => item.model_name),
      ]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    });
    return filtered.sort((left, right) => {
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
    effectiveFamilyFilter,
    groupRows,
    locale,
    search,
    sortBy,
    strategyFilter,
  ]);

  function resetFilters() {
    setFamilyFilter("all");
    setSearch("");
    setStrategyFilter("all");
    setSortBy("members-desc");
  }

  return {
    activeFilterCount: [
      effectiveFamilyFilter !== "all",
      Boolean(search.trim()),
      strategyFilter !== "all",
    ].filter(Boolean).length,
    effectiveFamilyFilter,
    familyOptions,
    resetFilters,
    search,
    setFamilyFilter,
    setSearch,
    setSortBy,
    setStrategyFilter,
    sortBy,
    strategyFilter,
    visibleGroups,
  };
}
