"use client";

import { useMemo, useState } from "react";
import type { RoutingStrategy } from "@/lib/api";
import { getModelFamilyKey } from "@/lib/ModelIcons";
import {
  buildModelPrefixOptions,
  resolveEffectiveModelPrefix,
  type SelectedModelPrefix,
} from "@/lib/modelPrefix";
import type { GroupRow, GroupSort } from "./modelGroupUtils";

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
