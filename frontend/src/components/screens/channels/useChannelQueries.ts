import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { apiRequest } from "@/lib/api/client";
import type { Site } from "@/lib/api/sites";
import { siteEndpointSummary, siteModelCounts } from "./channelModels";
import type {
  ChannelSort,
  ChannelStatusFilter,
  Locale,
  SiteRow,
} from "./channelTypes";

/** Loads channel data and derives the filtered channel list. */
export function useChannelQueries(locale: Locale) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ChannelStatusFilter>("all");
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<ChannelSort>("name-asc");
  const {
    data: sites,
    error: sitesError,
    isError: sitesIsError,
    isLoading,
  } = useQuery({
    queryKey: ["sites"],
    queryFn: () => apiRequest<Site[]>("/admin/sites"),
    staleTime: 2 * 60_000,
  });
  const siteRows = useMemo<SiteRow[]>(
    () =>
      (sites ?? []).map((site) => ({
        ...site,
        model_count: siteModelCounts(site).enabled,
        endpoint_summary: siteEndpointSummary(site, locale),
      })),
    [sites, locale],
  );
  const tags = useMemo(
    () =>
      Array.from(new Set((sites ?? []).flatMap((site) => site.tags))).sort(
        (left, right) => left.localeCompare(right, locale),
      ),
    [locale, sites],
  );
  const visibleSites = useMemo<SiteRow[]>(() => {
    const keyword = search.trim().toLowerCase();
    const filtered = siteRows.filter((site) => {
      if (statusFilter === "enabled" && !site.enabled) return false;
      if (statusFilter === "disabled" && site.enabled) return false;
      if (tagFilter && !site.tags.includes(tagFilter)) return false;
      if (!keyword) return true;
      return [
        site.name,
        site.endpoint_summary,
        ...site.tags,
        ...site.protocols.flatMap((config) =>
          config.models.map((model) => model.model_name),
        ),
      ]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    });
    return [...filtered].sort((left, right) => {
      if (sortBy === "name-asc")
        return left.name.localeCompare(right.name, locale);
      if (sortBy === "name-desc")
        return right.name.localeCompare(left.name, locale);
      if (sortBy === "models-desc")
        return (
          right.model_count - left.model_count ||
          left.name.localeCompare(right.name, locale)
        );
      return left.name.localeCompare(right.name, locale);
    });
  }, [locale, search, siteRows, sortBy, statusFilter, tagFilter]);

  async function invalidateChannelData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["sites"] }),
      queryClient.invalidateQueries({ queryKey: ["group-candidates"] }),
      queryClient.invalidateQueries({ queryKey: ["groups"] }),
      queryClient.invalidateQueries({ queryKey: ["request-logs"] }),
      queryClient.invalidateQueries({ queryKey: ["request-log-detail"] }),
      queryClient.invalidateQueries({
        queryKey: ["request-log-attempt-detail"],
      }),
    ]);
  }

  function resetFilters() {
    setSearch("");
    setStatusFilter("all");
    setTagFilter(null);
    setSortBy("name-asc");
  }

  return {
    queryClient,
    sitesError,
    sitesIsError,
    isLoading,
    visibleSites,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    tags,
    tagFilter,
    setTagFilter,
    sortBy,
    setSortBy,
    activeFilterCount: [
      Boolean(search.trim()),
      statusFilter !== "all",
      Boolean(tagFilter),
    ].filter(Boolean).length,
    resetFilters,
    invalidateChannelData,
  };
}
