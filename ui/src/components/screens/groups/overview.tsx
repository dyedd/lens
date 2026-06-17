"use client";

import type { Dispatch, SetStateAction } from "react";
import { Copy, Filter, GripVertical, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemFooter,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";
import { Combobox, ComboboxOption } from "@/components/ui/combobox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ToolbarSearchInput } from "@/components/ui/toolbar-search-input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { ModelGroup, ProtocolKind, RoutingStrategy } from "@/lib/api";
import { getModelGroupAvatar } from "@/lib/model-icons";
import { cn } from "@/lib/utils";
import { CompactPriceSummary, SeriesChip, StrategyToggle } from "./components";
import {
  credentialNumberLabel,
  isGroupEnabled,
  protocolBadgeClassName,
  protocolLabel,
  protocolOptions,
  type GroupRow,
  type GroupSort,
  type ModelPrefixOption,
  type SelectedModelPrefix,
} from "./shared";

export function GroupsOverview({
  locale,
  hasModelPrefixOptions,
  modelPrefixOptions,
  effectiveSelectedModelPrefix,
  setSelectedModelPrefix,
  isLoading,
  groupsIsError,
  visibleGroups,
  busyId,
  cardDragging,
  setCardDragging,
  search,
  protocolFilter,
  strategyFilter,
  sortBy,
  activeFilterCount,
  setSearch,
  setProtocolFilter,
  setStrategyFilter,
  setSortBy,
  resetFilters,
  openEdit,
  changeStrategy,
  reorderGroupMembers,
  removeGroupMember,
  toggleGroupEnabled,
  setDeleteTarget,
}: {
  locale: "zh-CN" | "en-US";
  hasModelPrefixOptions: boolean;
  modelPrefixOptions: ModelPrefixOption[];
  effectiveSelectedModelPrefix: SelectedModelPrefix;
  setSelectedModelPrefix: Dispatch<SetStateAction<SelectedModelPrefix>>;
  isLoading: boolean;
  groupsIsError: boolean;
  visibleGroups: GroupRow[];
  busyId: string | null;
  cardDragging: { groupId: string; index: number } | null;
  setCardDragging: Dispatch<
    SetStateAction<{ groupId: string; index: number } | null>
  >;
  search: string;
  protocolFilter: "all" | ProtocolKind;
  strategyFilter: "all" | RoutingStrategy;
  sortBy: GroupSort;
  activeFilterCount: number;
  setSearch: Dispatch<SetStateAction<string>>;
  setProtocolFilter: Dispatch<SetStateAction<"all" | ProtocolKind>>;
  setStrategyFilter: Dispatch<SetStateAction<"all" | RoutingStrategy>>;
  setSortBy: Dispatch<SetStateAction<GroupSort>>;
  resetFilters: () => void;
  openEdit: (item: ModelGroup) => void;
  changeStrategy: (group: GroupRow, strategy: RoutingStrategy) => void;
  reorderGroupMembers: (
    group: GroupRow,
    fromIndex: number,
    toIndex: number,
  ) => void;
  removeGroupMember: (group: GroupRow, memberKey: string) => void;
  toggleGroupEnabled: (group: GroupRow, enabled: boolean) => void;
  setDeleteTarget: Dispatch<SetStateAction<ModelGroup | null>>;
}) {
  const copyModelNameLabel =
    locale === "zh-CN" ? "复制模型名称" : "Copy model name";

  async function copyGroupName(name: string) {
    try {
      await navigator.clipboard.writeText(name);
      toast.success(
        locale === "zh-CN" ? "模型名称已复制" : "Model name copied",
      );
    } catch {
      toast.error(locale === "zh-CN" ? "复制失败" : "Failed to copy");
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_320px]">
      <div className="order-2 grid gap-4 xl:order-1">
        {hasModelPrefixOptions ? (
          <div className="rounded-2xl border bg-card px-4 py-3 sm:px-5 sm:py-4">
            <div className="flex items-center justify-between gap-3 sm:mb-3">
              <div>
                <div className="text-base font-semibold text-foreground">
                  {locale === "zh-CN" ? "选择模型系列" : "Choose model series"}
                </div>
              </div>
            </div>

            <Combobox
              className="mt-3 w-full sm:hidden"
              value={effectiveSelectedModelPrefix}
              onChange={(event) => setSelectedModelPrefix(event.target.value)}
            >
              {modelPrefixOptions.map((option) => (
                <ComboboxOption key={option.key} value={option.key}>
                  {option.label}
                </ComboboxOption>
              ))}
            </Combobox>

            <div className="hidden snap-x gap-3 overflow-x-auto pb-1 sm:flex">
              {modelPrefixOptions.map((option) => (
                <SeriesChip
                  key={option.key}
                  selected={effectiveSelectedModelPrefix === option.key}
                  label={option.label}
                  sampleModel={option.sampleModel}
                  isAll={option.key === "all"}
                  onClick={() => setSelectedModelPrefix(option.key)}
                />
              ))}
            </div>
          </div>
        ) : null}

        <Card className="overflow-hidden py-0 xl:min-h-[calc(100dvh-18rem)]">
          <CardContent className="px-3 py-3 xl:max-h-[calc(100dvh-18rem)] xl:overflow-y-auto">
            {isLoading || groupsIsError ? null : visibleGroups.length ? (
              <ItemGroup className="gap-3">
                {visibleGroups.map((group) => {
                  const GroupAvatar = getModelGroupAvatar(group.name);
                  return (
                    <Item
                      key={group.id}
                      variant="outline"
                      role="button"
                      tabIndex={0}
                      className="items-start gap-3 rounded-2xl border-border/80 bg-background px-4 py-4 shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer"
                      onClick={() => openEdit(group)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          openEdit(group);
                        }
                      }}
                    >
                      <ItemMedia
                        variant="icon"
                        className="mt-0.5 hidden size-11 self-start rounded-xl bg-muted/40 sm:flex"
                      >
                        <GroupAvatar size={30} />
                      </ItemMedia>
                      <ItemContent className="min-w-0">
                        <div className="flex flex-col gap-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <ItemTitle className="truncate text-base">
                              {group.name}
                            </ItemTitle>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon-xs"
                                  aria-label={copyModelNameLabel}
                                  className="-ml-1 text-muted-foreground hover:text-foreground"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void copyGroupName(group.name);
                                  }}
                                  onKeyDown={(event) => event.stopPropagation()}
                                >
                                  <Copy />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent side="bottom" align="start">
                                {copyModelNameLabel}
                              </TooltipContent>
                            </Tooltip>
                            <div className="flex flex-wrap gap-1.5">
                              {group.protocols.map((protocol) => (
                                <Badge
                                  key={protocol}
                                  variant="outline"
                                  className={cn(
                                    "px-2.5 py-0.5",
                                    protocolBadgeClassName(protocol),
                                  )}
                                >
                                  {protocolLabel(protocol, locale)}
                                </Badge>
                              ))}
                            </div>
                            {group.is_route_group ? (
                              <Badge
                                variant="outline"
                                className="px-2.5 py-0.5"
                              >
                                {locale === "zh-CN" ? "路由组" : "Route group"}
                              </Badge>
                            ) : null}
                          </div>
                          {group.is_route_group ? (
                            <ItemDescription className="text-sm">
                              {`${group.name} -> ${group.route_group_name || group.route_group_id || "n/a"}`}
                            </ItemDescription>
                          ) : (
                            <CompactPriceSummary
                              locale={locale}
                              inputPrice={group.input_price_per_million}
                              outputPrice={group.output_price_per_million}
                              cacheReadPrice={
                                group.cache_read_price_per_million
                              }
                              cacheWritePrice={
                                group.cache_write_price_per_million
                              }
                            />
                          )}
                        </div>
                        {!group.is_route_group ? (
                          <ItemFooter
                            className="mt-3 flex flex-wrap items-center gap-2.5"
                            onClick={(event) => event.stopPropagation()}
                            onKeyDown={(event) => event.stopPropagation()}
                          >
                            <StrategyToggle
                              value={group.strategy}
                              locale={locale}
                              disabled={busyId === group.id}
                              size="sm"
                              className="w-fit max-w-full"
                              onChange={(value) =>
                                void changeStrategy(group, value)
                              }
                            />
                          </ItemFooter>
                        ) : null}
                        <div
                          className="mt-3 flex flex-wrap items-center gap-2"
                          onClick={(event) => event.stopPropagation()}
                          onKeyDown={(event) => event.stopPropagation()}
                        >
                          {group.is_route_group ? (
                            <Badge variant="outline" className="px-3 py-1.5">
                              {group.route_group_name ||
                                group.route_group_id ||
                                "n/a"}
                            </Badge>
                          ) : group.display_members.length ? (
                            group.display_members.map((member, index) => {
                              const channelName =
                                member.channel_names.slice(0, 2).join(" · ") ||
                                "n/a";
                              const sourceLabel = `${channelName} · ${credentialNumberLabel(member, locale)}`;
                              return (
                                <div
                                  key={`${member.key}::${index}`}
                                  className={cn(
                                    "flex min-w-0 max-w-full items-center rounded-full border bg-background",
                                    !member.enabled && "opacity-55",
                                    cardDragging?.groupId === group.id &&
                                      cardDragging.index === index &&
                                      "opacity-60",
                                  )}
                                  title={`${sourceLabel} · ${member.model_name}`}
                                >
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    draggable={busyId !== group.id}
                                    className="h-auto min-w-0 max-w-full rounded-full rounded-r-none border-0 px-3 py-1.5 cursor-grab active:cursor-grabbing"
                                    onDragStart={() =>
                                      setCardDragging({
                                        groupId: group.id,
                                        index,
                                      })
                                    }
                                    onDragOver={(event) =>
                                      event.preventDefault()
                                    }
                                    onDrop={() => {
                                      if (
                                        !cardDragging ||
                                        cardDragging.groupId !== group.id
                                      )
                                        return;
                                      void reorderGroupMembers(
                                        group,
                                        cardDragging.index,
                                        index,
                                      );
                                    }}
                                    onDragEnd={() => setCardDragging(null)}
                                  >
                                    <GripVertical data-icon="inline-start" />
                                    <span className="min-w-0 truncate">
                                      {member.model_name}
                                    </span>
                                    <span className="min-w-0 truncate text-muted-foreground">
                                      · {sourceLabel}
                                    </span>
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon-xs"
                                    className="mr-1 shrink-0 rounded-full text-muted-foreground hover:text-destructive"
                                    disabled={busyId === group.id}
                                    onClick={() =>
                                      void removeGroupMember(group, member.key)
                                    }
                                  >
                                    <X />
                                  </Button>
                                </div>
                              );
                            })
                          ) : (
                            <ItemDescription className="text-sm">
                              {locale === "zh-CN" ? "暂无成员" : "No members"}
                            </ItemDescription>
                          )}
                        </div>
                      </ItemContent>
                      <ItemActions
                        className="basis-full flex-wrap justify-end self-start sm:ml-auto sm:basis-auto sm:shrink-0"
                        onClick={(event) => event.stopPropagation()}
                        onKeyDown={(event) => event.stopPropagation()}
                      >
                        <Switch
                          checked={isGroupEnabled(group)}
                          disabled={
                            group.is_route_group ||
                            busyId === group.id ||
                            !group.items.length
                          }
                          onCheckedChange={(checked) =>
                            void toggleGroupEnabled(group, checked)
                          }
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setDeleteTarget(group)}
                        >
                          <Trash2 data-icon="inline-start" />
                          {locale === "zh-CN" ? "删除" : "Delete"}
                        </Button>
                      </ItemActions>
                    </Item>
                  );
                })}
              </ItemGroup>
            ) : (
              <div className="rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">
                {effectiveSelectedModelPrefix !== "all" ||
                search.trim() ||
                protocolFilter !== "all" ||
                strategyFilter !== "all"
                  ? locale === "zh-CN"
                    ? "没有匹配的模型组。"
                    : "No matching groups."
                  : locale === "zh-CN"
                    ? "当前还没有模型组。"
                    : "No groups yet."}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <aside className="order-1 xl:order-2">
        <div className="rounded-2xl border bg-card p-4 xl:sticky xl:top-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex size-9 items-center justify-center rounded-xl bg-primary/[0.08] text-primary">
                <Filter size={16} />
              </span>
              <div>
                <div className="text-sm font-semibold text-foreground">
                  {locale === "zh-CN" ? "筛选" : "Filters"}
                </div>
                <div className="text-xs text-muted-foreground">
                  {locale === "zh-CN"
                    ? `已启用 ${activeFilterCount} 项`
                    : `${activeFilterCount} active`}
                </div>
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              disabled={!activeFilterCount && sortBy === "members-desc"}
            >
              {locale === "zh-CN" ? "清空" : "Clear"}
            </Button>
          </div>

          <FieldSet className="gap-4">
            <FieldLegend>
              {locale === "zh-CN" ? "筛选条件" : "Refine results"}
            </FieldLegend>
            <FieldGroup className="gap-4">
              <Field>
                <FieldLabel>
                  {locale === "zh-CN" ? "关键词" : "Keyword"}
                </FieldLabel>
                <ToolbarSearchInput
                  value={search}
                  onChange={setSearch}
                  onClear={() => setSearch("")}
                  placeholder={
                    locale === "zh-CN"
                      ? "模型组 / 渠道 / 模型"
                      : "Group / channel / model"
                  }
                  className="max-w-none"
                />
              </Field>

              <Field>
                <FieldLabel>
                  {locale === "zh-CN" ? "协议" : "Protocol"}
                </FieldLabel>
                <Select
                  value={protocolFilter}
                  onValueChange={(value) =>
                    setProtocolFilter(value as "all" | ProtocolKind)
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">
                      {locale === "zh-CN" ? "全部协议" : "All protocols"}
                    </SelectItem>
                    {protocolOptions(locale).map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <Field>
                <FieldLabel>
                  {locale === "zh-CN" ? "策略" : "Strategy"}
                </FieldLabel>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {[
                    {
                      key: "all" as const,
                      label: locale === "zh-CN" ? "全部" : "All",
                    },
                    {
                      key: "round_robin" as const,
                      label: locale === "zh-CN" ? "轮询" : "Round Robin",
                    },
                    {
                      key: "failover" as const,
                      label: locale === "zh-CN" ? "故障转移" : "Failover",
                    },
                  ].map((option) => (
                    <Button
                      key={option.key}
                      type="button"
                      variant={
                        strategyFilter === option.key ? "default" : "outline"
                      }
                      size="sm"
                      onClick={() => setStrategyFilter(option.key)}
                    >
                      {option.label}
                    </Button>
                  ))}
                </div>
              </Field>

              <Field>
                <FieldLabel>{locale === "zh-CN" ? "排序" : "Sort"}</FieldLabel>
                <Select
                  value={sortBy}
                  onValueChange={(value) => setSortBy(value as GroupSort)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="members-desc">
                      {locale === "zh-CN" ? "成员优先" : "Members first"}
                    </SelectItem>
                    <SelectItem value="enabled-desc">
                      {locale === "zh-CN" ? "启用优先" : "Enabled first"}
                    </SelectItem>
                    <SelectItem value="name-asc">
                      {locale === "zh-CN" ? "名称 A-Z" : "Name A-Z"}
                    </SelectItem>
                    <SelectItem value="name-desc">
                      {locale === "zh-CN" ? "名称 Z-A" : "Name Z-A"}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            </FieldGroup>
          </FieldSet>
        </div>
      </aside>
    </div>
  );
}
