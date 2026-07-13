"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  ProtocolKind,
  RouteSnapshot,
  Site,
  SiteRuntimeSummary,
} from "@/lib/api";
import { apiRequest } from "@/lib/api";
import {
  isSiteEnabled,
  siteEndpointSummary,
  siteModelCount,
  siteSubtitle,
  type ChannelSort,
  type ChannelStatusFilter,
  type Locale,
  type SiteRow,
} from "./channelShared";

/** Loads channel data and derives the filtered channel list. */
export function useChannelQueries(locale: Locale) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ChannelStatusFilter>("all");
  const [protocolFilter, setProtocolFilter] = useState<"all" | ProtocolKind>(
    "all",
  );
  const [sortBy, setSortBy] = useState<ChannelSort>("requests-desc");
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
  const { data: siteRuntimeSummaries } = useQuery({
    queryKey: ["site-runtime-summaries"],
    queryFn: () => apiRequest<SiteRuntimeSummary[]>("/admin/sites/runtime"),
    staleTime: 5_000,
    refetchInterval: 5000,
  });
  const { data: routerSnapshot } = useQuery({
    queryKey: ["router-snapshot"],
    queryFn: () => apiRequest<RouteSnapshot>("/admin/routes"),
    staleTime: 5_000,
    refetchInterval: 5000,
  });
  const siteRuntimeById = useMemo(
    () =>
      new Map(
        (siteRuntimeSummaries ?? []).map(
          (item) => [item.site_id, item] as const,
        ),
      ),
    [siteRuntimeSummaries],
  );
  const channelHealthById = useMemo(
    () =>
      new Map(
        (routerSnapshot?.health ?? []).map(
          (item) => [item.channel_id, item] as const,
        ),
      ),
    [routerSnapshot],
  );
  const siteRows = useMemo<SiteRow[]>(
    () =>
      (sites ?? []).map((site) => ({
        ...site,
        subtitle: siteSubtitle(site, locale),
        enabled_protocol_channel_count: site.protocols.reduce(
          (total, protocolConfig) =>
            protocolConfig.enabled
              ? total + protocolConfig.protocols.length
              : total,
          0,
        ),
        model_count: siteModelCount(site),
        endpoint_summary: siteEndpointSummary(site, locale),
      })),
    [sites, locale],
  );
  const visibleSites = useMemo<SiteRow[]>(() => {
    const keyword = search.trim().toLowerCase();
    const filtered = siteRows.filter((site) => {
      if (statusFilter === "enabled" && !isSiteEnabled(site)) return false;
      if (statusFilter === "disabled" && isSiteEnabled(site)) return false;
      if (
        protocolFilter !== "all" &&
        !site.protocols.some(
          (config) =>
            config.enabled && config.protocols.includes(protocolFilter),
        )
      ) {
        return false;
      }
      if (!keyword) return true;
      return [
        site.name,
        site.subtitle,
        site.endpoint_summary,
        ...site.protocols.flatMap((config) =>
          config.models.map((model) => model.model_name),
        ),
      ]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    });
    return [...filtered].sort((left, right) => {
      const leftRequests =
        siteRuntimeById.get(left.id)?.recent_request_count ?? 0;
      const rightRequests =
        siteRuntimeById.get(right.id)?.recent_request_count ?? 0;
      if (sortBy === "name-asc")
        return left.name.localeCompare(right.name, locale);
      if (sortBy === "name-desc")
        return right.name.localeCompare(left.name, locale);
      if (sortBy === "models-desc")
        return (
          right.model_count - left.model_count ||
          left.name.localeCompare(right.name, locale)
        );
      if (sortBy === "protocols-desc")
        return (
          right.enabled_protocol_channel_count -
            left.enabled_protocol_channel_count ||
          left.name.localeCompare(right.name, locale)
        );
      return (
        rightRequests - leftRequests ||
        left.name.localeCompare(right.name, locale)
      );
    });
  }, [
    locale,
    protocolFilter,
    search,
    siteRows,
    siteRuntimeById,
    sortBy,
    statusFilter,
  ]);

  async function invalidateChannelData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["sites"] }),
      queryClient.invalidateQueries({ queryKey: ["site-runtime-summaries"] }),
      queryClient.invalidateQueries({ queryKey: ["router-snapshot"] }),
      queryClient.invalidateQueries({ queryKey: ["group-candidates"] }),
      queryClient.invalidateQueries({ queryKey: ["groups"] }),
      queryClient.invalidateQueries({ queryKey: ["model-groups"] }),
    ]);
  }

  function resetFilters() {
    setSearch("");
    setStatusFilter("all");
    setProtocolFilter("all");
    setSortBy("requests-desc");
  }

  return {
    queryClient,
    sitesError,
    sitesIsError,
    isLoading,
    siteRuntimeById,
    channelHealthById,
    visibleSites,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    protocolFilter,
    setProtocolFilter,
    sortBy,
    setSortBy,
    activeFilterCount: [
      Boolean(search.trim()),
      statusFilter !== "all",
      protocolFilter !== "all",
    ].filter(Boolean).length,
    resetFilters,
    invalidateChannelData,
  };
}
