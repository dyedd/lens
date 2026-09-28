import {
  ArrowDownUp,
  Check,
  Funnel,
  Plus,
  RefreshCw,
  Search,
  Shuffle,
} from "lucide-react";
import { useState } from "react";
import {
  BulkActionButton,
  BulkActionsPopover,
} from "@/components/ui/BulkActionsPopover";
import { Button } from "@/components/ui/Button";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { Input } from "@/components/ui/Input";
import { TablePagination } from "@/components/ui/Pagination";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { ToolbarButton } from "@/components/ui/ToolbarButton";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { useClientPagination } from "@/hooks/useClientPagination";
import { useRowSelection } from "@/hooks/useRowSelection";
import type {
  ModelGroup,
  RoutingStrategy,
  UnplacedModel,
} from "@/lib/api/groups";
import type { ProtocolKind } from "@/lib/api/protocols";
import { cn } from "@/lib/classNames";
import type { ModelPrefixOption, SelectedModelPrefix } from "@/lib/modelPrefix";
import { GroupsTable } from "./GroupsTable";
import type { GroupRow, GroupSort, SimilarGroupView } from "./groupTypes";
import { STRATEGY_OPTIONS } from "./modelGroupFormatting";
import { UnplacedModelsPanel } from "./UnplacedModelsPanel";

const groupId = (group: GroupRow) => group.id;

function groupSortOptions(
  locale: "zh-CN" | "en-US",
): Array<{ value: GroupSort; label: string }> {
  return [
    {
      value: "members-desc",
      label: locale === "zh-CN" ? "成员优先" : "Members first",
    },
    {
      value: "enabled-desc",
      label: locale === "zh-CN" ? "启用优先" : "Enabled first",
    },
    { value: "name-asc", label: locale === "zh-CN" ? "名称升序" : "Name A-Z" },
    { value: "name-desc", label: locale === "zh-CN" ? "名称降序" : "Name Z-A" },
  ];
}

type MergeRequest = { source: GroupRow; target: SimilarGroupView };

type Props = {
  locale: "zh-CN" | "en-US";
  visibleGroups: GroupRow[];
  unplacedModels: UnplacedModel[];
  joinableGroupIds: Set<string>;
  isLoading: boolean;
  search: string;
  strategyFilter: "all" | RoutingStrategy;
  sortBy: GroupSort;
  activeFilterCount: number;
  familyOptions: ModelPrefixOption[];
  familyFilter: SelectedModelPrefix;
  protocolOptions: Array<{ value: ProtocolKind; label: string }>;
  protocolFilter: "all" | ProtocolKind;
  busyId: string | null;
  testingModel: boolean;
  onSearchChange: (value: string) => void;
  onStrategyChange: (value: "all" | RoutingStrategy) => void;
  onSortChange: (value: GroupSort) => void;
  onFamilyChange: (value: SelectedModelPrefix) => void;
  onProtocolChange: (value: "all" | ProtocolKind) => void;
  onReset: () => void;
  onRefresh: () => void;
  onCreate: () => void;
  onOpenEdit: (group: ModelGroup) => void;
  onToggleEnabled: (group: GroupRow, enabled: boolean) => void;
  onChangeStrategy: (group: GroupRow, strategy: RoutingStrategy) => void;
  onMerge: (source: ModelGroup, target: SimilarGroupView) => Promise<void>;
  onDelete: (group: ModelGroup) => void;
  onTest: (group: GroupRow) => void;
  onBulkEnabled: (groups: GroupRow[], enabled: boolean) => void;
  onBulkStrategy: (groups: GroupRow[], strategy: RoutingStrategy) => void;
  onBulkDelete: (groups: ModelGroup[]) => void;
  onAddModelsToGroup: (groupId: string, modelNames: string[]) => void;
  onCreateGroupForModels: (name: string, modelNames: string[]) => void;
  onAutoPlace: () => void;
  onRemoveUnplacedModels: (modelNames: string[]) => Promise<boolean>;
};

/** Renders unplaced models and the model group list as a toolbar and table. */
export function GroupsOverview({
  locale,
  visibleGroups,
  unplacedModels,
  joinableGroupIds,
  isLoading,
  search,
  strategyFilter,
  sortBy,
  activeFilterCount,
  familyOptions,
  familyFilter,
  protocolOptions,
  protocolFilter,
  busyId,
  testingModel,
  onSearchChange,
  onStrategyChange,
  onSortChange,
  onFamilyChange,
  onProtocolChange,
  onReset,
  onRefresh,
  onCreate,
  onOpenEdit,
  onToggleEnabled,
  onChangeStrategy,
  onMerge,
  onDelete,
  onTest,
  onBulkEnabled,
  onBulkStrategy,
  onBulkDelete,
  onAddModelsToGroup,
  onCreateGroupForModels,
  onAutoPlace,
  onRemoveUnplacedModels,
}: Props) {
  const {
    pageRows: pagedGroups,
    resetPage,
    paginationProps,
  } = useClientPagination(visibleGroups);
  const selection = useRowSelection(visibleGroups, groupId);
  const selectedGroups = selection.selectedRows;
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [mergeRequest, setMergeRequest] = useState<MergeRequest | null>(null);
  const sortOptions = groupSortOptions(locale);

  return (
    <div className="space-y-3 pb-10">
      <div className="flex min-h-10 items-center justify-between gap-3 px-1">
        <h3 className="min-w-0 text-sm font-semibold">
          {locale === "zh-CN" ? "模型组管理" : "Model groups"}
        </h3>
      </div>

      {unplacedModels.length ? (
        <UnplacedModelsPanel
          locale={locale}
          unplacedModels={unplacedModels}
          busyId={busyId}
          joinableGroupIds={joinableGroupIds}
          onAddModelsToGroup={onAddModelsToGroup}
          onCreateGroupForModels={onCreateGroupForModels}
          onAutoPlace={onAutoPlace}
          onRemoveModels={onRemoveUnplacedModels}
        />
      ) : null}

      <section className="flex min-h-10 flex-nowrap items-center gap-1.5 overflow-x-auto overscroll-x-contain py-1 [scrollbar-width:none] md:gap-3 [&::-webkit-scrollbar]:hidden">
        <div className="flex min-w-max flex-nowrap items-center gap-1.5 md:min-w-0 md:flex-1">
          <div className="relative min-w-[160px] flex-1 md:max-w-[320px]">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              placeholder={
                locale === "zh-CN"
                  ? "搜索模型组、渠道或描述"
                  : "Search groups or channels"
              }
              onChange={(event) => {
                onSearchChange(event.target.value);
                resetPage();
              }}
              className="bg-background pl-8"
            />
          </div>

          <Popover>
            <PopoverTrigger asChild>
              <ToolbarButton
                aria-label={locale === "zh-CN" ? "筛选" : "Filter"}
              >
                <Funnel className="size-3.5" />
                <span className="hidden sm:inline">
                  {locale === "zh-CN" ? "筛选" : "Filter"}
                </span>
                {activeFilterCount ? (
                  <span className="text-[10px] tabular-nums">
                    {activeFilterCount}
                  </span>
                ) : null}
              </ToolbarButton>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-[240px] p-2">
              <div className="space-y-2">
                <div className="space-y-1">
                  <p className="px-1 text-[10px] text-muted-foreground">
                    {locale === "zh-CN" ? "策略" : "Strategy"}
                  </p>
                  <Select
                    value={strategyFilter}
                    onValueChange={(value) => {
                      onStrategyChange(value as "all" | RoutingStrategy);
                      resetPage();
                    }}
                  >
                    <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        {locale === "zh-CN" ? "全部策略" : "All strategies"}
                      </SelectItem>
                      <SelectItem value="round_robin">
                        {locale === "zh-CN" ? "轮询" : "Round robin"}
                      </SelectItem>
                      <SelectItem value="failover">
                        {locale === "zh-CN" ? "故障转移" : "Failover"}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {familyOptions.length ? (
                  <div className="space-y-1">
                    <p className="px-1 text-[10px] text-muted-foreground">
                      {locale === "zh-CN" ? "厂商" : "Family"}
                    </p>
                    <Select
                      value={familyFilter}
                      onValueChange={(value) => {
                        onFamilyChange(value);
                        resetPage();
                      }}
                    >
                      <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          {locale === "zh-CN" ? "全部厂商" : "All families"}
                        </SelectItem>
                        {familyOptions.map((option) => (
                          <SelectItem key={option.key} value={option.key}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : null}
                {protocolOptions.length ? (
                  <div className="space-y-1">
                    <p className="px-1 text-[10px] text-muted-foreground">
                      {locale === "zh-CN" ? "协议" : "Protocol"}
                    </p>
                    <Select
                      value={protocolFilter}
                      onValueChange={(value) => {
                        onProtocolChange(value as "all" | ProtocolKind);
                        resetPage();
                      }}
                    >
                      <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          {locale === "zh-CN" ? "全部协议" : "All protocols"}
                        </SelectItem>
                        {protocolOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : null}
                {activeFilterCount ? (
                  <div className="flex justify-end border-t border-border/60 pt-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs shadow-none"
                      onClick={() => {
                        onReset();
                        resetPage();
                      }}
                    >
                      {locale === "zh-CN" ? "清空" : "Clear"}
                    </Button>
                  </div>
                ) : null}
              </div>
            </PopoverContent>
          </Popover>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <ToolbarButton aria-label={locale === "zh-CN" ? "排序" : "Sort"}>
                <ArrowDownUp className="size-3.5" />
                <span className="hidden sm:inline">
                  {locale === "zh-CN" ? "排序" : "Sort"}
                </span>
              </ToolbarButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-40 p-1.5">
              {sortOptions.map((option) => (
                <DropdownMenuItem
                  key={option.value}
                  className="h-6 gap-2 px-2 py-0 text-[10px]"
                  onSelect={() => onSortChange(option.value)}
                >
                  <span className="flex-1 truncate">{option.label}</span>
                  {sortBy === option.value ? (
                    <Check className="size-3 text-muted-foreground" />
                  ) : null}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <BulkActionsPopover
            locale={locale}
            count={selectedGroups.length}
            isBusy={Boolean(busyId)}
            onSetEnabled={(enabled) => {
              void onBulkEnabled(selectedGroups, enabled);
              selection.clear();
            }}
            onDelete={() => setBulkDeleteOpen(true)}
          >
            {STRATEGY_OPTIONS.map((option) => (
              <BulkActionButton
                key={option.value}
                icon={<Shuffle className="size-3.5" />}
                label={
                  locale === "zh-CN"
                    ? `设为${option.zh}`
                    : `Set to ${option.en}`
                }
                isBusy={Boolean(busyId)}
                onClick={() => {
                  void onBulkStrategy(selectedGroups, option.value);
                  selection.clear();
                }}
              />
            ))}
          </BulkActionsPopover>
        </div>

        <div className="ml-auto flex min-h-8 shrink-0 items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <ToolbarButton
                onClick={onRefresh}
                disabled={isLoading}
                aria-label={locale === "zh-CN" ? "刷新" : "Refresh"}
              >
                <RefreshCw
                  className={cn("size-3.5", isLoading && "animate-spin")}
                />
              </ToolbarButton>
            </TooltipTrigger>
            <TooltipContent>
              {locale === "zh-CN" ? "刷新" : "Refresh"}
            </TooltipContent>
          </Tooltip>
          <Button
            type="button"
            size="sm"
            className="h-7 gap-1 text-xs"
            onClick={onCreate}
          >
            <Plus className="size-3.5" />
            {locale === "zh-CN" ? "新增" : "Add"}
          </Button>
        </div>
      </section>

      <GroupsTable
        locale={locale}
        items={pagedGroups}
        loading={isLoading}
        selected={selection.selected}
        busyId={busyId}
        testingModel={testingModel}
        onSelectAll={(checked) => selection.toggleRows(pagedGroups, checked)}
        onSelectOne={selection.toggleId}
        onEdit={onOpenEdit}
        onToggleEnabled={onToggleEnabled}
        onChangeStrategy={onChangeStrategy}
        onRequestMerge={(source, target) => setMergeRequest({ source, target })}
        onDelete={onDelete}
        onTest={onTest}
      />

      <TablePagination locale={locale} {...paginationProps} />

      <Dialog
        open={Boolean(mergeRequest)}
        onOpenChange={(open) => {
          if (!open) setMergeRequest(null);
        }}
      >
        <AppDialogContent
          className="max-w-lg"
          showCloseButton={false}
          title={locale === "zh-CN" ? "确认合并模型组" : "Merge groups"}
          description={
            locale === "zh-CN"
              ? `将「${mergeRequest?.source.name ?? ""}」的名称、匹配规则和成员并入「${mergeRequest?.target.name ?? ""}」，引用改指向目标组，然后删除「${mergeRequest?.source.name ?? ""}」。`
              : `Move the name, match rules and members of "${mergeRequest?.source.name ?? ""}" into "${mergeRequest?.target.name ?? ""}", repoint references, then delete "${mergeRequest?.source.name ?? ""}".`
          }
          footer={
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setMergeRequest(null)}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={Boolean(busyId)}
                onClick={() => {
                  if (!mergeRequest) return;
                  void onMerge(mergeRequest.source, mergeRequest.target);
                  setMergeRequest(null);
                }}
              >
                {locale === "zh-CN" ? "确认合并" : "Merge"}
              </Button>
            </>
          }
        />
      </Dialog>

      <ConfirmDeleteDialog
        open={bulkDeleteOpen}
        locale={locale}
        title={locale === "zh-CN" ? "确认批量删除" : "Delete groups"}
        description={
          locale === "zh-CN"
            ? `将删除选中的 ${selectedGroups.length} 个模型组。`
            : `${selectedGroups.length} selected groups will be removed.`
        }
        isDisabled={Boolean(busyId)}
        onOpenChange={setBulkDeleteOpen}
        onConfirm={() => {
          void onBulkDelete(selectedGroups);
          selection.clear();
          setBulkDeleteOpen(false);
        }}
      />
    </div>
  );
}
