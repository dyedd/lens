"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Plus, RefreshCcw } from "lucide-react";
import { toast } from "sonner";
import {
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupCandidatesPayload,
  ModelGroupCandidatesResponse,
  ProtocolKind,
  RoutingStrategy,
  Site,
  apiRequest,
  isItemValidForProtocols,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { getModelFamilyKey } from "@/lib/model-icons";
import {
  buildModelPrefixOptions,
  resolveEffectiveModelPrefix,
} from "@/lib/model-prefix";
import { DashboardHeaderActions } from "@/components/shell/dashboard-header-actions";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  apiErrorMessage,
  buildGroupDisplayMembers,
  candidatePayloadToFormItems,
  compileCandidateRegex,
  emptyForm,
  isGroupEnabled,
  itemKey,
  matchesCandidateSearch,
  modelFoldKey,
  moveItems,
  protocolBaseUrl,
  protocolConfigIdFromChannelId,
  toForm,
  toPayload,
  type CandidateChannelGroup,
  type CandidateSearchMode,
  type FoldedMember,
  type FormItem,
  type FormState,
  type GroupRow,
  type GroupSort,
  type ProtocolMeta,
  type SelectedModelPrefix,
} from "./groups/shared";
import { GroupsOverview } from "./groups/overview";

const GroupEditorDialog = dynamic(() =>
  import("./groups/dialogs").then((module) => module.GroupEditorDialog),
);
const DeleteGroupDialog = dynamic(() =>
  import("./groups/dialogs").then((module) => module.DeleteGroupDialog),
);

export function GroupsScreen() {
  const queryClient = useQueryClient();
  const { locale } = useI18n();
  const [selectedModelPrefix, setSelectedModelPrefix] =
    useState<SelectedModelPrefix>("all");
  const [search, setSearch] = useState("");
  const [protocolFilter, setProtocolFilter] = useState<"all" | ProtocolKind>(
    "all",
  );
  const [strategyFilter, setStrategyFilter] = useState<"all" | RoutingStrategy>(
    "all",
  );
  const [sortBy, setSortBy] = useState<GroupSort>("members-desc");
  const [candidateSearchMode, setCandidateSearchMode] =
    useState<CandidateSearchMode>("contains");
  const [candidateSearch, setCandidateSearch] = useState("");
  const [candidateSearchUsesGroupName, setCandidateSearchUsesGroupName] =
    useState(true);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null);
  const [expandedChannels, setExpandedChannels] = useState<string[]>([]);
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [cardDragging, setCardDragging] = useState<{
    groupId: string;
    index: number;
  } | null>(null);
  const [showEnabledOnly, setShowEnabledOnly] = useState(false);
  const [syncingPrices, setSyncingPrices] = useState(false);
  const {
    data: groups,
    error: groupsError,
    isError: groupsIsError,
    isLoading,
  } = useQuery({
    queryKey: ["groups"],
    queryFn: () => apiRequest<ModelGroup[]>("/admin/model-groups"),
    staleTime: 2 * 60_000,
  });
  const {
    data: sites,
    error: sitesError,
    isError: sitesIsError,
  } = useQuery({
    queryKey: ["sites"],
    queryFn: () => apiRequest<Site[]>("/admin/sites"),
    staleTime: 2 * 60_000,
  });
  const candidatePayload: ModelGroupCandidatesPayload = useMemo(
    () => ({
      protocols: form.protocols,
      exclude_items: form.items.map((item) => ({
        channel_id: item.channel_id,
        credential_id: item.credential_id,
        model_name: item.model_name,
        enabled: item.enabled,
      })),
    }),
    [form.items, form.protocols],
  );
  const {
    data: candidateResponse,
    error: candidateError,
    isError: candidateIsError,
    refetch: refetchCandidates,
    isFetching: isFetchingCandidates,
  } = useQuery({
    queryKey: ["group-candidates", candidatePayload],
    queryFn: () =>
      apiRequest<ModelGroupCandidatesResponse>(
        "/admin/model-group-candidates",
        {
          method: "POST",
          body: JSON.stringify(candidatePayload),
        },
      ),
    enabled: dialogOpen && !form.route_group_id && form.protocols.length > 0,
  });

  const channelMap = useMemo(() => {
    const map = new Map<string, ProtocolMeta>();
    for (const site of sites ?? []) {
      for (const protocolConfig of site.protocols) {
        const baseUrl = site.base_urls.find(
          (b) => b.id === protocolConfig.base_url_id,
        );
        const baseUrlStr =
          baseUrl?.url ?? protocolBaseUrl(site, protocolConfig.base_url_id);
        for (const p of protocolConfig.protocols) {
          const runtimeChannelId = `${protocolConfig.id}_${p}`;
          map.set(runtimeChannelId, {
            id: runtimeChannelId,
            site_id: site.id,
            name: site.name,
            base_url: baseUrlStr,
            protocol: p,
          });
        }
        if (
          !map.has(protocolConfig.id) &&
          protocolConfig.protocols.length > 0
        ) {
          map.set(protocolConfig.id, {
            id: protocolConfig.id,
            site_id: site.id,
            name: site.name,
            base_url: baseUrlStr,
            protocol: protocolConfig.protocols[0],
          });
        }
      }
    }
    return map;
  }, [sites]);

  const groupRows = useMemo<GroupRow[]>(
    () =>
      (groups ?? []).map((group) => {
        const isRouteGroup = Boolean(group.route_group_id);
        const items = group.items
          .slice()
          .sort((a, b) => a.sort_order - b.sort_order);
        const displayMembers = isRouteGroup
          ? []
          : buildGroupDisplayMembers(items, channelMap);
        const channelNames = isRouteGroup
          ? [group.route_group_name || group.route_group_id || ""]
          : [
              ...new Set(
                items
                  .map(
                    (item) =>
                      channelMap.get(item.channel_id)?.name ||
                      item.channel_name ||
                      item.channel_id,
                  )
                  .filter(Boolean),
              ),
            ];
        return {
          ...group,
          items,
          member_count: isRouteGroup ? 1 : displayMembers.length,
          enabled_member_count: isRouteGroup
            ? 1
            : displayMembers.filter((member) => member.enabled).length,
          channel_summary: channelNames.slice(0, 2).join(" · "),
          channel_names: channelNames,
          display_members: displayMembers,
          is_route_group: isRouteGroup,
        };
      }),
    [channelMap, groups],
  );

  const routeTargetOptions = useMemo(
    () =>
      (groups ?? [])
        .filter(
          (group) =>
            form.protocols.every((protocol) =>
              group.protocols.includes(protocol),
            ) &&
            !group.route_group_id &&
            group.id !== editingId,
        )
        .sort((left, right) => left.name.localeCompare(right.name, locale)),
    [editingId, form.protocols, groups, locale],
  );

  const modelPrefixOptions = useMemo(
    () =>
      buildModelPrefixOptions(
        groupRows.map((group) => group.name),
        locale,
      ),
    [groupRows, locale],
  );
  const hasModelPrefixOptions = modelPrefixOptions.length > 0;

  const effectiveSelectedModelPrefix = resolveEffectiveModelPrefix(
    modelPrefixOptions,
    selectedModelPrefix,
  );

  const visibleGroups = useMemo<GroupRow[]>(() => {
    const keyword = search.trim().toLowerCase();
    const filtered = groupRows.filter((group) => {
      if (
        effectiveSelectedModelPrefix !== "all" &&
        getModelFamilyKey(group.name) !== effectiveSelectedModelPrefix
      )
        return false;
      if (protocolFilter !== "all" && !group.protocols.includes(protocolFilter))
        return false;
      if (strategyFilter !== "all" && group.strategy !== strategyFilter)
        return false;
      if (!keyword) return true;
      const haystack = [
        group.name,
        group.channel_summary,
        ...group.channel_names,
        ...group.items.map((item) => item.model_name),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(keyword);
    });

    return [...filtered].sort((left, right) => {
      if (sortBy === "name-asc")
        return left.name.localeCompare(right.name, locale);
      if (sortBy === "name-desc")
        return right.name.localeCompare(left.name, locale);
      if (sortBy === "enabled-desc")
        return (
          right.enabled_member_count - left.enabled_member_count ||
          left.name.localeCompare(right.name, locale)
        );
      return (
        right.member_count - left.member_count ||
        left.name.localeCompare(right.name, locale)
      );
    });
  }, [
    effectiveSelectedModelPrefix,
    groupRows,
    locale,
    protocolFilter,
    search,
    sortBy,
    strategyFilter,
  ]);
  const activeFilterCount = [
    effectiveSelectedModelPrefix !== "all",
    Boolean(search.trim()),
    protocolFilter !== "all",
    strategyFilter !== "all",
  ].filter(Boolean).length;
  const candidateRegexInvalid =
    candidateSearchMode === "regex" &&
    Boolean(candidateSearch.trim()) &&
    !compileCandidateRegex(candidateSearch);

  const filteredCandidates = useMemo(() => {
    return (candidateResponse?.candidates ?? []).filter((item) => {
      return matchesCandidateSearch(
        item,
        candidateSearchMode,
        candidateSearch,
        channelMap,
        locale,
      );
    });
  }, [
    candidateResponse,
    candidateSearch,
    candidateSearchMode,
    channelMap,
    locale,
  ]);

  const groupedCandidates = useMemo(() => {
    const groupsBySite = new Map<string, CandidateChannelGroup>();

    for (const candidate of filteredCandidates) {
      const channel = channelMap.get(candidate.channel_id);
      const channelName = channel?.name || candidate.channel_name;
      const groupKey =
        candidate.protocol_config_id ||
        channel?.site_id ||
        candidate.site_id ||
        candidate.channel_id;
      let existing = groupsBySite.get(groupKey);
      if (!existing) {
        existing = {
          key: groupKey,
          site_id: channel?.site_id || candidate.site_id,
          channel_name: channelName,
          candidates: [],
        };
        groupsBySite.set(groupKey, existing);
      }
      existing.candidates.push(candidate);
    }

    return Array.from(groupsBySite.values()).sort((a, b) =>
      a.channel_name.localeCompare(b.channel_name, locale),
    );
  }, [channelMap, filteredCandidates, locale]);

  const candidateListError = candidateIsError ? candidateError : sitesError;

  const foldedMembers = useMemo<FoldedMember[]>(() => {
    const orderMap = new Map<string, number>();
    const memberMap = new Map<string, FoldedMember>();

    for (const item of form.items) {
      const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
      const key = modelFoldKey(
        protocolConfigId,
        item.credential_id,
        item.model_name,
      );
      if (!memberMap.has(key)) {
        orderMap.set(key, orderMap.size);
        memberMap.set(key, {
          key,
          protocolConfigId,
          model_name: item.model_name,
          credential_id: item.credential_id,
          credential_name: item.credential_name,
          credential_number: item.credential_number,
          protocols: [],
          subItems: [],
          enabled: false,
          invalid: false,
        });
      }
      const member = memberMap.get(key)!;
      member.subItems.push(item);
      if (item.enabled) member.enabled = true;
      if (item.protocol && !member.protocols.includes(item.protocol)) {
        member.protocols.push(item.protocol);
      }
    }

    for (const member of memberMap.values()) {
      member.invalid = member.subItems.every(
        (sub) =>
          !sub.protocol ||
          !isItemValidForProtocols(sub.protocol, form.protocols),
      );
    }

    return Array.from(orderMap.entries())
      .sort((a, b) => a[1] - b[1])
      .map(([key]) => memberMap.get(key)!);
  }, [form.items, form.protocols]);

  const visibleFoldedMembers = useMemo(() => {
    if (!showEnabledOnly) {
      return foldedMembers.map((member, index) => ({ member, index }));
    }
    return foldedMembers.flatMap((member, index) =>
      member.enabled ? [{ member, index }] : [],
    );
  }, [foldedMembers, showEnabledOnly]);

  const invalidSelectedMemberCount = useMemo(
    () => foldedMembers.filter((m) => m.invalid).length,
    [foldedMembers],
  );

  useEffect(() => {
    if (!dialogOpen) {
      setCandidateSearch("");
      setCandidateSearchMode("contains");
      setCandidateSearchUsesGroupName(true);
      setExpandedChannels([]);
      setDraggingIndex(null);
    }
  }, [dialogOpen]);

  useEffect(() => {
    if (
      !dialogOpen ||
      candidateSearchMode !== "contains" ||
      !candidateSearchUsesGroupName
    ) {
      return;
    }
    setCandidateSearch(form.name);
  }, [
    candidateSearchMode,
    candidateSearchUsesGroupName,
    dialogOpen,
    form.name,
  ]);

  useEffect(() => {
    if (!groupedCandidates.length) {
      setExpandedChannels([]);
      return;
    }
    setExpandedChannels((current) => {
      const available = new Set(groupedCandidates.map((item) => item.key));
      const filtered = current.filter((item) => available.has(item));
      if (filtered.length) {
        return filtered;
      }
      return [groupedCandidates[0].key];
    });
  }, [groupedCandidates]);

  useEffect(() => {
    if (!groupsIsError) return;
    toast.error(
      locale === "zh-CN" ? "模型组加载失败" : "Failed to load groups",
      {
        id: "groups-load-error",
        description:
          groupsError instanceof Error
            ? groupsError.message
            : locale === "zh-CN"
              ? "无法读取模型组"
              : "Unable to read groups",
      },
    );
  }, [groupsError, groupsIsError, locale]);

  async function invalidateGroupData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["groups"] }),
      queryClient.invalidateQueries({ queryKey: ["sites"] }),
      queryClient.invalidateQueries({ queryKey: ["group-candidates"] }),
    ]);
  }

  function openCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setCandidateSearch("");
    setCandidateSearchMode("contains");
    setCandidateSearchUsesGroupName(true);
    setDialogOpen(true);
  }

  function openEdit(item: ModelGroup) {
    const hasSavedFilter = Boolean(
      item.sync_filter_mode && item.sync_filter_query.trim(),
    );
    setEditingId(item.id);
    setForm(toForm(item));
    setCandidateSearch(hasSavedFilter ? item.sync_filter_query : item.name);
    setCandidateSearchMode(
      item.sync_filter_mode === "regex" ? "regex" : "contains",
    );
    setCandidateSearchUsesGroupName(
      !hasSavedFilter && item.sync_filter_mode !== "regex",
    );
    setDialogOpen(true);
  }

  async function saveGroup(payload: FormState, groupId: string | null) {
    const savedGroup = await apiRequest<ModelGroup>(
      groupId ? "/admin/model-groups/" + groupId : "/admin/model-groups",
      {
        method: groupId ? "PUT" : "POST",
        body: JSON.stringify(toPayload(payload)),
      },
    );
    await invalidateGroupData();
    return savedGroup;
  }

  async function saveGroupPrice(
    groupName: string,
    payload: {
      input_price_per_million: number;
      output_price_per_million: number;
      cache_read_price_per_million: number;
      cache_write_price_per_million: number;
    },
  ) {
    await apiRequest("/admin/model-prices/" + encodeURIComponent(groupName), {
      method: "PUT",
      body: JSON.stringify({
        model_key: groupName,
        display_name: groupName,
        ...payload,
      }),
    });
    await queryClient.invalidateQueries({ queryKey: ["groups"] });
  }

  function parsePriceForm(payload: FormState) {
    const input = Number(payload.input_price_per_million);
    const output = Number(payload.output_price_per_million);
    const cacheRead = Number(payload.cache_read_price_per_million);
    const cacheWrite = Number(payload.cache_write_price_per_million);

    if (
      !Number.isFinite(input) ||
      input < 0 ||
      !Number.isFinite(output) ||
      output < 0 ||
      !Number.isFinite(cacheRead) ||
      cacheRead < 0 ||
      !Number.isFinite(cacheWrite) ||
      cacheWrite < 0
    ) {
      throw new Error(
        locale === "zh-CN"
          ? "价格必须是大于等于 0 的数字"
          : "Prices must be numbers greater than or equal to 0",
      );
    }

    return {
      input_price_per_million: input,
      output_price_per_million: output,
      cache_read_price_per_million: cacheRead,
      cache_write_price_per_million: cacheWrite,
    };
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.protocols.length) {
      toast.error(
        locale === "zh-CN"
          ? "至少需要选择一项协议。"
          : "At least one protocol is required.",
      );
      return;
    }
    if (!form.route_group_id && invalidSelectedMemberCount > 0) {
      toast.error(
        locale === "zh-CN"
          ? "请先移除不适用于所选协议的失效节点"
          : "Please remove invalid nodes invalid for the selected protocols",
      );
      return;
    }
    try {
      const savedGroup = await saveGroup(form, editingId);
      if (!savedGroup.route_group_id) {
        const pricePayload = parsePriceForm(form);
        await saveGroupPrice(savedGroup.name, pricePayload);
      }
      toast.success(
        editingId
          ? locale === "zh-CN"
            ? "模型组已更新"
            : "Group updated"
          : locale === "zh-CN"
            ? "模型组已创建"
            : "Group created",
      );
      setDialogOpen(false);
      setEditingId(null);
      setForm(emptyForm);
    } catch (e) {
      toast.error(
        apiErrorMessage(
          e,
          locale === "zh-CN" ? "保存模型组失败" : "Failed to save group",
        ),
      );
    }
  }

  async function syncPrices() {
    setSyncingPrices(true);
    try {
      await apiRequest("/admin/model-price-sync-jobs", { method: "POST" });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
      toast.success(
        locale === "zh-CN" ? "模型价格已同步" : "Model prices synced",
      );
    } catch (e) {
      toast.error(
        apiErrorMessage(
          e,
          locale === "zh-CN"
            ? "同步模型价格失败"
            : "Failed to sync model prices",
        ),
      );
    } finally {
      setSyncingPrices(false);
    }
  }

  async function remove(item: ModelGroup) {
    setBusyId(item.id);
    try {
      await apiRequest<void>("/admin/model-groups/" + item.id, {
        method: "DELETE",
      });
      setDeleteTarget(null);
      await invalidateGroupData();
      toast.success(locale === "zh-CN" ? "模型组已删除" : "Group deleted");
    } catch (e) {
      toast.error(
        apiErrorMessage(
          e,
          locale === "zh-CN" ? "删除模型组失败" : "Failed to delete group",
        ),
      );
    } finally {
      setBusyId(null);
    }
  }

  function addCandidate(candidate: ModelGroupCandidateItem) {
    const newFormItems = candidatePayloadToFormItems(candidate, channelMap);
    setForm((current) => {
      const existingKeys = new Set(current.items.map((m) => itemKey(m)));
      const toAdd = newFormItems.filter((fi) => !existingKeys.has(itemKey(fi)));
      if (!toAdd.length) return current;
      return { ...current, items: [...current.items, ...toAdd] };
    });
  }

  function removeFoldedMember(foldKey: string) {
    setForm((current) => {
      const toRemove = new Set<string>();
      for (const item of current.items) {
        const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
        if (
          modelFoldKey(
            protocolConfigId,
            item.credential_id,
            item.model_name,
          ) === foldKey
        ) {
          toRemove.add(itemKey(item));
        }
      }
      return {
        ...current,
        items: current.items.filter((item) => !toRemove.has(itemKey(item))),
      };
    });
  }

  function toggleFoldedMember(foldKey: string, enabled: boolean) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item) => {
        const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
        if (
          modelFoldKey(
            protocolConfigId,
            item.credential_id,
            item.model_name,
          ) === foldKey
        ) {
          return { ...item, enabled };
        }
        return item;
      }),
    }));
  }

  function moveFoldedMember(fromIndex: number, toIndex: number) {
    setForm((current) => {
      const orderMap = new Map<string, number>();
      const memberMap = new Map<string, FormItem[]>();
      for (const item of current.items) {
        const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
        const key = modelFoldKey(
          protocolConfigId,
          item.credential_id,
          item.model_name,
        );
        if (!memberMap.has(key)) {
          orderMap.set(key, orderMap.size);
          memberMap.set(key, []);
        }
        memberMap.get(key)!.push(item);
      }
      const orderedKeys = Array.from(orderMap.entries())
        .sort((a, b) => a[1] - b[1])
        .map(([k]) => k);
      const nextKeys = moveItems(orderedKeys, fromIndex, toIndex);
      if (nextKeys === orderedKeys) return current;
      const nextItems = nextKeys.flatMap((k) => memberMap.get(k) ?? []);
      return { ...current, items: nextItems };
    });
  }

  async function updateGroupPartial(
    group: ModelGroup,
    updates: Partial<FormState>,
  ) {
    setBusyId(group.id);
    try {
      await saveGroup({ ...toForm(group), ...updates }, group.id);
      return true;
    } catch (e) {
      toast.error(
        apiErrorMessage(
          e,
          locale === "zh-CN" ? "更新模型组失败" : "Failed to update group",
        ),
      );
      return false;
    } finally {
      setBusyId(null);
    }
  }

  async function reorderGroupMembers(
    group: GroupRow,
    fromIndex: number,
    toIndex: number,
  ) {
    if (group.is_route_group || fromIndex === toIndex || busyId === group.id) {
      return;
    }
    const nextMembers = moveItems(group.display_members, fromIndex, toIndex);
    if (nextMembers === group.display_members) {
      return;
    }
    const nextItems = nextMembers.flatMap((member) =>
      member.items.map((item) => ({
        channel_id: item.channel_id,
        channel_name: item.channel_name,
        protocol: item.protocol,
        credential_id: item.credential_id,
        credential_name: item.credential_name,
        credential_number: item.credential_number,
        model_name: item.model_name,
        enabled: item.enabled,
      })),
    );
    await updateGroupPartial(group, { items: nextItems });
  }

  async function changeStrategy(group: GroupRow, strategy: RoutingStrategy) {
    if (
      group.is_route_group ||
      busyId === group.id ||
      group.strategy === strategy
    ) {
      return;
    }
    const updated = await updateGroupPartial(group, { strategy });
    if (updated) {
      toast.success(locale === "zh-CN" ? "策略已更新" : "Strategy updated");
    }
  }

  async function toggleGroupEnabled(group: GroupRow, enabled: boolean) {
    if (
      group.is_route_group ||
      !group.items.length ||
      busyId === group.id ||
      isGroupEnabled(group) === enabled
    ) {
      return;
    }
    const nextItems = toForm(group).items.map((item) => ({ ...item, enabled }));
    const updated = await updateGroupPartial(group, { items: nextItems });
    if (updated) {
      toast.success(
        enabled
          ? locale === "zh-CN"
            ? "模型组已启动"
            : "Group enabled"
          : locale === "zh-CN"
            ? "模型组已停止"
            : "Group disabled",
      );
    }
  }

  async function removeGroupMember(group: GroupRow, memberKey: string) {
    if (group.is_route_group || busyId === group.id) {
      return;
    }
    const member = group.display_members.find((item) => item.key === memberKey);
    if (!member) {
      return;
    }
    const removedKeys = new Set(member.items.map((item) => itemKey(item)));
    const nextItems = toForm(group).items.filter(
      (item) => !removedKeys.has(itemKey(item)),
    );
    const updated = await updateGroupPartial(group, { items: nextItems });
    if (updated) {
      toast.success(locale === "zh-CN" ? "成员已删除" : "Member removed");
    }
  }

  function toggleChannel(channelId: string) {
    setExpandedChannels((current) =>
      current.includes(channelId)
        ? current.filter((item) => item !== channelId)
        : [...current, channelId],
    );
  }

  function addMatchedItems() {
    if (!filteredCandidates.length && !candidateSearch.trim()) {
      return;
    }
    setForm((current) => {
      const existing = new Set(current.items.map((item) => itemKey(item)));
      const additions = filteredCandidates.flatMap((candidate) =>
        candidatePayloadToFormItems(candidate, channelMap).filter(
          (fi) => !existing.has(itemKey(fi)),
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
    if (!form.sync_filter_mode || !form.sync_filter_query.trim()) {
      return;
    }
    const regex =
      form.sync_filter_mode === "regex"
        ? compileCandidateRegex(form.sync_filter_query)
        : null;
    if (form.sync_filter_mode === "regex" && !regex) {
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
      const previous = new Map(form.items.map((item) => [itemKey(item), item]));
      const matchedFormItems: FormItem[] = [];
      const seenKeys = new Set<string>();
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
        const expanded = candidatePayloadToFormItems(candidate, channelMap);
        for (const fi of expanded) {
          const k = itemKey(fi);
          if (seenKeys.has(k)) continue;
          seenKeys.add(k);
          const old = previous.get(k);
          matchedFormItems.push(old ? { ...fi, enabled: old.enabled } : fi);
        }
      }
      const existingKeys = new Set(
        form.items.map((item) => itemKey(item)).filter((k) => seenKeys.has(k)),
      );
      const existingItems = matchedFormItems.filter((fi) =>
        existingKeys.has(itemKey(fi)),
      );
      const newItems = matchedFormItems.filter(
        (fi) => !existingKeys.has(itemKey(fi)),
      );
      const nextItems = [...existingItems, ...newItems];
      setForm((current) => ({ ...current, items: nextItems }));
      toast.success(
        locale === "zh-CN"
          ? `已按规则更新 ${nextItems.length} 个模型，保存后生效`
          : `Updated ${nextItems.length} models by rule. Save to apply`,
      );
    } catch (e) {
      toast.error(
        apiErrorMessage(
          e,
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

  function changeCandidateSearchMode(mode: CandidateSearchMode) {
    setCandidateSearchMode(mode);
    if (mode === "contains") {
      setCandidateSearch(form.name);
      setCandidateSearchUsesGroupName(true);
      return;
    }
    setCandidateSearchUsesGroupName(false);
  }

  function changeCandidateSearch(value: string) {
    setCandidateSearch(value);
    setCandidateSearchUsesGroupName(false);
  }

  function toggleProtocol(protocol: ProtocolKind) {
    setForm((current) => ({
      ...current,
      protocols: current.protocols.includes(protocol)
        ? current.protocols.filter((item) => item !== protocol)
        : [...current.protocols, protocol],
    }));
  }

  function changeRouteTarget(routeGroupId: string) {
    setForm((current) => ({
      ...current,
      route_group_id: routeGroupId,
      sync_filter_mode: routeGroupId ? "" : current.sync_filter_mode,
      sync_filter_query: routeGroupId ? "" : current.sync_filter_query,
    }));
    setExpandedChannels([]);
  }

  function setAllMembersEnabled(enabled: boolean) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item) => ({ ...item, enabled })),
    }));
  }

  function removeInvalidItems() {
    const invalidKeys = new Set(
      foldedMembers.filter((m) => m.invalid).map((m) => m.key),
    );
    setForm((current) => ({
      ...current,
      items: current.items.filter((item) => {
        const protocolConfigId = protocolConfigIdFromChannelId(item.channel_id);
        const key = modelFoldKey(
          protocolConfigId,
          item.credential_id,
          item.model_name,
        );
        return !invalidKeys.has(key);
      }),
    }));
  }

  function resetFilters() {
    setSelectedModelPrefix("all");
    setSearch("");
    setProtocolFilter("all");
    setStrategyFilter("all");
    setSortBy("members-desc");
  }

  const syncPricesLabel = syncingPrices
    ? locale === "zh-CN"
      ? "同步中..."
      : "Syncing..."
    : locale === "zh-CN"
      ? "同步价格"
      : "Sync prices";
  const createGroupLabel =
    locale === "zh-CN" ? "新增模型组" : "New model group";

  return (
    <>
      <DashboardHeaderActions>
        <div className="flex items-center justify-end gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={syncPricesLabel}
                onClick={() => void syncPrices()}
                disabled={syncingPrices}
              >
                <RefreshCcw
                  data-icon="inline-start"
                  className={syncingPrices ? "animate-spin" : ""}
                />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {syncPricesLabel}
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon-sm"
                type="button"
                variant="ghost"
                aria-label={createGroupLabel}
                onClick={openCreate}
              >
                <Plus />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {createGroupLabel}
            </TooltipContent>
          </Tooltip>
        </div>
      </DashboardHeaderActions>

      <section className="flex flex-col gap-4">
        <GroupsOverview
          locale={locale}
          hasModelPrefixOptions={hasModelPrefixOptions}
          modelPrefixOptions={modelPrefixOptions}
          effectiveSelectedModelPrefix={effectiveSelectedModelPrefix}
          setSelectedModelPrefix={setSelectedModelPrefix}
          isLoading={isLoading}
          groupsIsError={groupsIsError}
          visibleGroups={visibleGroups}
          busyId={busyId}
          cardDragging={cardDragging}
          setCardDragging={setCardDragging}
          search={search}
          protocolFilter={protocolFilter}
          strategyFilter={strategyFilter}
          sortBy={sortBy}
          activeFilterCount={activeFilterCount}
          setSearch={setSearch}
          setProtocolFilter={setProtocolFilter}
          setStrategyFilter={setStrategyFilter}
          setSortBy={setSortBy}
          resetFilters={resetFilters}
          openEdit={openEdit}
          changeStrategy={changeStrategy}
          reorderGroupMembers={reorderGroupMembers}
          removeGroupMember={removeGroupMember}
          toggleGroupEnabled={toggleGroupEnabled}
          setDeleteTarget={setDeleteTarget}
        />

        {dialogOpen ? (
          <GroupEditorDialog
            dialogOpen={dialogOpen}
            setDialogOpen={setDialogOpen}
            editingId={editingId}
            locale={locale}
            submit={submit}
            form={form}
            setForm={setForm}
            toggleProtocol={toggleProtocol}
            routeTargetOptions={routeTargetOptions}
            changeRouteTarget={changeRouteTarget}
            candidateSearchMode={candidateSearchMode}
            changeCandidateSearchMode={changeCandidateSearchMode}
            candidateSearch={candidateSearch}
            changeCandidateSearch={changeCandidateSearch}
            addMatchedItems={addMatchedItems}
            candidateRegexInvalid={candidateRegexInvalid}
            filteredCandidates={filteredCandidates}
            refetchCandidates={refetchCandidates}
            isFetchingCandidates={isFetchingCandidates}
            applySavedFilter={applySavedFilter}
            clearSavedFilter={clearSavedFilter}
            groupedCandidates={groupedCandidates}
            expandedChannels={expandedChannels}
            toggleChannel={toggleChannel}
            foldedMembers={foldedMembers}
            addCandidate={addCandidate}
            sitesIsError={sitesIsError}
            candidateIsError={candidateIsError}
            candidateListError={candidateListError}
            invalidSelectedMemberCount={invalidSelectedMemberCount}
            removeInvalidItems={removeInvalidItems}
            setAllMembersEnabled={setAllMembersEnabled}
            showEnabledOnly={showEnabledOnly}
            setShowEnabledOnly={setShowEnabledOnly}
            visibleFoldedMembers={visibleFoldedMembers}
            draggingIndex={draggingIndex}
            toggleFoldedMember={toggleFoldedMember}
            removeFoldedMember={removeFoldedMember}
            setDraggingIndex={setDraggingIndex}
            moveFoldedMember={moveFoldedMember}
          />
        ) : null}

        {deleteTarget ? (
          <DeleteGroupDialog
            deleteTarget={deleteTarget}
            locale={locale}
            busyId={busyId}
            setDeleteTarget={setDeleteTarget}
            remove={remove}
          />
        ) : null}
      </section>
    </>
  );
}
