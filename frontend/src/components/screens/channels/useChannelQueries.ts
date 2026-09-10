import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { apiRequest } from "@/lib/api/client";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { Site } from "@/lib/api/sites";
import {
  isSiteProtocolConfigEnabled,
  siteEndpointSummary,
  siteModelCount,
} from "./channelModels";
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
  const [protocolFilter, setProtocolFilter] = useState<"all" | ProtocolKind>(
    "all",
  );
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
        enabled_protocol_channel_count: site.enabled
          ? site.protocols.reduce(
              (total, protocolConfig) =>
                isSiteProtocolConfigEnabled(site, protocolConfig)
                  ? total + protocolConfig.protocols.length
                  : total,
              0,
            )
          : 0,
        model_count: siteModelCount(site),
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
      if (
        protocolFilter !== "all" &&
        !site.protocols.some(
          (config) =>
            isSiteProtocolConfigEnabled(site, config) &&
            config.protocols.includes(protocolFilter),
        )
      ) {
        return false;
      }
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
      if (sortBy === "protocols-desc")
        return (
          right.enabled_protocol_channel_count -
            left.enabled_protocol_channel_count ||
          left.name.localeCompare(right.name, locale)
        );
      return left.name.localeCompare(right.name, locale);
    });
  }, [
    locale,
    protocolFilter,
    search,
    siteRows,
    sortBy,
    statusFilter,
    tagFilter,
  ]);

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
    setProtocolFilter("all");
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
    protocolFilter,
    setProtocolFilter,
    tags,
    tagFilter,
    setTagFilter,
    sortBy,
    setSortBy,
    activeFilterCount: [
      Boolean(search.trim()),
      statusFilter !== "all",
      protocolFilter !== "all",
      Boolean(tagFilter),
    ].filter(Boolean).length,
    resetFilters,
    invalidateChannelData,
  };
}

import type { SiteModelInput } from "@/lib/api/sites";
import {
  aggregateModelGroupKey,
  baseUrlLabel,
  credentialLabel,
  protocolConfigDisplayName,
  protocolConfigModelKey,
  syncTargetKey,
} from "./channelModels";
import type {
  FormBaseUrl,
  FormCredential,
  FormProtocolConfig,
} from "./channelTypes";

export type AggregatedModelMember = {
  /** Per-credential key matching protocolConfigModelKey semantics. */
  key: string;
  credentialName: string;
  source: SiteModelInput["source"];
  isTargetOnly: boolean;
};

export type AggregatedModel = {
  /** Group key shared by every same-name model inside one protocol config. */
  key: string;
  modelName: string;
  protocols: ProtocolKind[];
  sourceLabel: string;
  source: SiteModelInput["source"];
  /** Per-credential rows for expanding the collapsed overview row. */
  members: AggregatedModelMember[];
  /** Per-credential key used to open the single-model test dialog. */
  testKey: string | null;
};

type ModelGroupSeed = {
  modelName: string;
  protocols: Set<ProtocolKind>;
  sources: Set<SiteModelInput["source"]>;
  members: AggregatedModelMember[];
  testKey: string | null;
};

/**
 * Builds the channel overview rows, collapsing models that share a name
 * within one protocol configuration so multi-key duplicates stay one row.
 */
export function useAggregatedModels(
  protocolConfigs: FormProtocolConfig[],
  baseUrls: FormBaseUrl[],
  credentials: FormCredential[],
  locale: Locale,
): AggregatedModel[] {
  return useMemo(() => {
    const credentialNameById = new Map(
      credentials.map(
        (credential, index) =>
          [credential.id, credentialLabel(credential, index, locale)] as const,
      ),
    );
    const credentialName = (credentialId: string) =>
      credentialNameById.get(credentialId) ||
      (locale === "zh-CN" ? "未知密钥" : "Unknown key");
    return protocolConfigs.flatMap((protocolConfig, index) => {
      const baseUrlIndex = baseUrls.findIndex(
        (item) => item.id === protocolConfig.base_url_id,
      );
      const baseUrl = baseUrlIndex >= 0 ? baseUrls[baseUrlIndex] : undefined;
      const protocolConfigName = protocolConfigDisplayName(
        protocolConfig,
        index,
        locale,
      );
      const sourceName = baseUrl
        ? `${protocolConfigName} · ${baseUrlLabel(baseUrl, baseUrlIndex, locale)}`
        : protocolConfigName;
      const groups = new Map<string, ModelGroupSeed>();
      const groupOf = (modelName: string) => {
        const existing = groups.get(modelName);
        if (existing) return existing;
        const created: ModelGroupSeed = {
          modelName,
          protocols: new Set(),
          sources: new Set(),
          members: [],
          testKey: null,
        };
        groups.set(modelName, created);
        return created;
      };
      const addMember = (
        group: ModelGroupSeed,
        memberKey: string,
        credentialId: string,
        source: SiteModelInput["source"],
        isTargetOnly: boolean,
      ) => {
        const existing = group.members.find(
          (member) => member.key === memberKey,
        );
        if (existing) {
          existing.isTargetOnly = existing.isTargetOnly && isTargetOnly;
          return;
        }
        group.members.push({
          key: memberKey,
          credentialName: credentialName(credentialId),
          source,
          isTargetOnly,
        });
        if (!group.testKey && !isTargetOnly) group.testKey = memberKey;
      };

      for (const model of protocolConfig.models) {
        const group = groupOf(model.model_name);
        for (const protocol of model.protocols) {
          group.protocols.add(protocol);
        }
        group.sources.add(model.source);
        addMember(
          group,
          protocolConfigModelKey(protocolConfig, model),
          model.credential_id,
          model.source,
          false,
        );
      }

      const syncedProtocolKeys = new Set(
        protocolConfig.models
          .filter((model) => model.source === "synced")
          .flatMap((model) =>
            model.protocols.map((protocol) =>
              syncTargetKey({
                credential_id: model.credential_id,
                model_name: model.model_name,
                protocol,
              }),
            ),
          ),
      );
      for (const target of protocolConfig.sync_targets) {
        if (syncedProtocolKeys.has(syncTargetKey(target))) continue;
        const group = groupOf(target.model_name);
        group.protocols.add(target.protocol);
        group.sources.add("synced");
        addMember(
          group,
          protocolConfigModelKey(protocolConfig, {
            ...target,
            source: "synced",
          }),
          target.credential_id,
          "synced",
          true,
        );
      }

      return Array.from(groups.values()).map((group) => ({
        key: aggregateModelGroupKey(protocolConfig, group.modelName),
        modelName: group.modelName,
        protocols: Array.from(group.protocols),
        sourceLabel: `${sourceName} · ${group.members
          .map((member) => member.credentialName)
          .join(locale === "zh-CN" ? "、" : ", ")}`,
        source: group.sources.has("manual") ? "manual" : "synced",
        members: group.members,
        testKey: group.testKey,
      }));
    });
  }, [baseUrls, credentials, protocolConfigs, locale]);
}
