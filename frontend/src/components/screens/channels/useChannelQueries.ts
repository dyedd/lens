import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { apiRequest } from "@/lib/api/client";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { Site, SiteModelInput } from "@/lib/api/sites";
import {
  activeBaseUrlValue,
  protocolConfigSelectedCredentialIds,
} from "./channelForm";
import {
  aggregateModelGroupKey,
  credentialLabel,
  formatCredentialTitle,
  protocolConfigModelKey,
  siteEndpointSummary,
  siteModelCounts,
} from "./channelModels";
import type {
  ChannelSort,
  ChannelStatusFilter,
  FormState,
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
      queryClient.invalidateQueries({ queryKey: ["model-groups"] }),
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

export type AggregatedModelMember = {
  /** Per-credential key matching protocolConfigModelKey semantics. */
  key: string;
  credentialId: string;
  credentialName: string;
  /** Key label plus masked value. */
  credentialTitle: string;
  source: SiteModelInput["source"];
};

export type AggregatedModel = {
  /** Group key shared by every same-name model inside one protocol config. */
  key: string;
  modelName: string;
  /** Base URL of the protocol config that owns this row. */
  baseUrl: string;
  /** Number of keys bound to the owning protocol config. */
  credentialCount: number;
  protocols: ProtocolKind[];
  source: SiteModelInput["source"];
  enabled: boolean;
  upstreamMissing: boolean;
  /** Per-credential rows for expanding the collapsed overview row. */
  members: AggregatedModelMember[];
  /** Per-credential key used to open the single-model test dialog. */
  testKey: string | null;
};

type ModelGroupSeed = {
  modelName: string;
  protocols: Set<ProtocolKind>;
  sources: Set<SiteModelInput["source"]>;
  enabled: boolean;
  upstreamMissing: boolean;
  members: AggregatedModelMember[];
  testKey: string | null;
};

/**
 * Builds the channel overview rows, collapsing models that share a name
 * within one protocol configuration so multi-key duplicates stay one row.
 */
export function useAggregatedModels(
  form: Pick<FormState, "base_urls" | "credentials" | "protocolConfigs">,
  locale: Locale,
): AggregatedModel[] {
  const { base_urls: baseUrls, credentials, protocolConfigs } = form;
  return useMemo(() => {
    const credentialById = new Map(
      credentials.map(
        (credential, index) => [credential.id, { credential, index }] as const,
      ),
    );
    const unknownKey = locale === "zh-CN" ? "未知密钥" : "Unknown key";
    const credentialNames = (credentialId: string) => {
      const entry = credentialById.get(credentialId);
      if (!entry) return { name: unknownKey, title: unknownKey };
      return {
        name: credentialLabel(entry.credential, entry.index, locale),
        title: formatCredentialTitle(entry.credential, entry.index, locale),
      };
    };
    return protocolConfigs.flatMap((protocolConfig) => {
      const baseUrl = activeBaseUrlValue(
        { base_urls: baseUrls },
        protocolConfig,
      ).trim();
      const credentialCount =
        protocolConfigSelectedCredentialIds(protocolConfig).length;
      const groups = new Map<string, ModelGroupSeed>();
      const groupOf = (modelName: string) => {
        const existing = groups.get(modelName);
        if (existing) return existing;
        const created: ModelGroupSeed = {
          modelName,
          protocols: new Set(),
          sources: new Set(),
          enabled: false,
          upstreamMissing: false,
          members: [],
          testKey: null,
        };
        groups.set(modelName, created);
        return created;
      };

      for (const model of protocolConfig.models) {
        const group = groupOf(model.model_name);
        for (const protocol of model.protocols) {
          group.protocols.add(protocol);
        }
        group.sources.add(model.source);
        group.enabled = group.enabled || model.enabled;
        group.upstreamMissing = group.upstreamMissing || model.upstream_missing;
        const memberKey = protocolConfigModelKey(protocolConfig, model);
        if (group.members.some((member) => member.key === memberKey)) continue;
        const names = credentialNames(model.credential_id);
        group.members.push({
          key: memberKey,
          credentialId: model.credential_id,
          credentialName: names.name,
          credentialTitle: names.title,
          source: model.source,
        });
        group.testKey ??= memberKey;
      }

      return Array.from(groups.values()).map((group) => ({
        key: aggregateModelGroupKey(protocolConfig, group.modelName),
        modelName: group.modelName,
        baseUrl,
        credentialCount,
        protocols: Array.from(group.protocols),
        source: group.sources.has("manual") ? "manual" : "synced",
        enabled: group.enabled,
        upstreamMissing: group.upstreamMissing,
        members: group.members,
        testKey: group.testKey,
      }));
    });
  }, [baseUrls, credentials, protocolConfigs, locale]);
}
