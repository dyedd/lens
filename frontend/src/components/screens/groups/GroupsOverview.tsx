import {
  ArrowDownUp,
  Check,
  History,
  Plus,
  RefreshCw,
  Search,
  Shuffle,
} from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { FilterPillGroup } from "@/components/ui/FilterPillGroup";
import { Input } from "@/components/ui/Input";
import { TablePagination } from "@/components/ui/Pagination";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { SelectionActionBar } from "@/components/ui/SelectionActionBar";
import { useClientPagination } from "@/hooks/useClientPagination";
import { useRowSelection } from "@/hooks/useRowSelection";
import type {
  ModelGroup,
  RoutingStrategy,
  UnplacedModel,
} from "@/lib/api/groups";
import { cn } from "@/lib/classNames";
import { titleForLocale } from "@/lib/I18nContext";
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
      label: titleForLocale(locale, "成员数量", "Member count"),
    },
    {
      value: "enabled-desc",
      label: titleForLocale(locale, "可用状态", "Availability"),
    },
    {
      value: "name-asc",
      label: titleForLocale(locale, "模型组名称升序", "Group name A-Z"),
    },
    {
      value: "name-desc",
      label: titleForLocale(locale, "模型组名称降序", "Group name Z-A"),
    },
  ];
}

type MergeRequest = { source: GroupRow; target: SimilarGroupView };

type Props = {
  locale: "zh-CN" | "en-US";
  visibleGroups: GroupRow[];
  unplacedModels: UnplacedModel[];
  joinableGroupIds: Set<string>;
  /** Join targets for the panel's multi-select bulk action. */
  joinableGroups: Array<{ id: string; name: string }>;
  isLoading: boolean;
  search: string;
  strategyFilter: "all" | RoutingStrategy;
  sortBy: GroupSort;
  activeFilterCount: number;
  familyOptions: ModelPrefixOption[];
  familyFilter: SelectedModelPrefix;
  busyId: string | null;
  testingModel: boolean;
  onSearchChange: (value: string) => void;
  onStrategyChange: (value: "all" | RoutingStrategy) => void;
  onSortChange: (value: GroupSort) => void;
  onFamilyChange: (value: SelectedModelPrefix) => void;
  onReset: () => void;
  onRefresh: () => void;
  onCreate: () => void;
  onOpenEdit: (group: ModelGroup) => void;
  onToggleEnabled: (group: GroupRow, enabled: boolean) => void;
  onChangeStrategy: (group: GroupRow, strategy: RoutingStrategy) => void;
  onMerge: (source: ModelGroup, target: SimilarGroupView) => Promise<boolean>;
  onDelete: (group: ModelGroup) => void;
  onTest: (group: GroupRow) => void;
  onBulkEnabled: (groups: GroupRow[], enabled: boolean) => void;
  onBulkStrategy: (groups: GroupRow[], strategy: RoutingStrategy) => void;
  onBulkDelete: (groups: ModelGroup[]) => void;
  onAddModelsToGroup: (groupId: string, modelNames: string[]) => void;
  onCreateGroupForModels: (name: string, modelNames: string[]) => void;
  onCreateOwnGroups: (modelNames: string[]) => Promise<boolean>;
  onAutoPlace: () => void;
  onRemoveUnplacedModels: (modelNames: string[]) => Promise<boolean>;
  onOpenSyncRuns: () => void;
};

/** Renders unplaced models and the model group list as a toolbar and table. */
export function GroupsOverview({
  locale,
  visibleGroups,
  unplacedModels,
  joinableGroupIds,
  joinableGroups,
  isLoading,
  search,
  strategyFilter,
  sortBy,
  activeFilterCount,
  familyOptions,
  familyFilter,
  busyId,
  testingModel,
  onSearchChange,
  onStrategyChange,
  onSortChange,
  onFamilyChange,
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
  onCreateOwnGroups,
  onAutoPlace,
  onRemoveUnplacedModels,
  onOpenSyncRuns,
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
  const searchPlaceholder =
    locale === "zh-CN"
      ? "搜索模型组、渠道或模型..."
      : "Search groups, channels, or models...";

  return (
    <div className="space-y-4 pb-10">
      <PageHeader
        title={locale === "zh-CN" ? "模型组" : "Model Groups"}
        actions={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
              onClick={onRefresh}
              disabled={isLoading}
              aria-label={locale === "zh-CN" ? "刷新" : "Refresh"}
            >
              <RefreshCw
                className={cn("size-3.5", isLoading && "animate-spin")}
              />
              {locale === "zh-CN" ? "刷新" : "Refresh"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
              onClick={onOpenSyncRuns}
            >
              <History className="size-3.5" />
              {locale === "zh-CN" ? "同步记录" : "Sync history"}
            </Button>
            <Button type="button" size="sm" onClick={onCreate}>
              <Plus className="size-3.5" />
              {locale === "zh-CN" ? "新建模型组" : "New Model Group"}
            </Button>
          </>
        }
      />

      {unplacedModels.length ? (
        <UnplacedModelsPanel
          locale={locale}
          unplacedModels={unplacedModels}
          busyId={busyId}
          joinableGroupIds={joinableGroupIds}
          joinableGroups={joinableGroups}
          onAddModelsToGroup={onAddModelsToGroup}
          onCreateGroupForModels={onCreateGroupForModels}
          onCreateOwnGroups={onCreateOwnGroups}
          onAutoPlace={onAutoPlace}
          onRemoveModels={onRemoveUnplacedModels}
        />
      ) : null}

      <section className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <FilterPillGroup
            value={strategyFilter}
            ariaLabel={locale === "zh-CN" ? "分发策略筛选" : "Strategy filter"}
            onValueChange={(value) => {
              onStrategyChange(value);
              resetPage();
            }}
            options={[
              {
                value: "all",
                label: locale === "zh-CN" ? "全部" : "All",
              },
              {
                value: "failover",
                label: locale === "zh-CN" ? "故障切换" : "Failover",
              },
              {
                value: "round_robin",
                label: locale === "zh-CN" ? "平滑轮询" : "Round robin",
              },
            ]}
          />

          {familyOptions.length ? (
            <Select
              value={familyFilter}
              onValueChange={(value) => {
                onFamilyChange(value);
                resetPage();
              }}
            >
              <SelectTrigger className="h-8 w-auto min-w-[104px] border-0 bg-transparent px-2 text-[13px] text-muted-foreground shadow-none hover:bg-muted/50 hover:text-foreground">
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
          ) : null}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-label={locale === "zh-CN" ? "排序" : "Sort"}
                className="h-8 rounded-xl border-border/70 px-2.5 text-[13px] font-medium"
              >
                <ArrowDownUp className="size-3.5 text-muted-foreground" />
                <span>
                  {sortOptions.find((o) => o.value === sortBy)?.label ??
                    (locale === "zh-CN" ? "排序" : "Sort")}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-40 p-1.5">
              {sortOptions.map((option) => (
                <DropdownMenuItem
                  key={option.value}
                  className="h-7 gap-2 px-2 py-0 text-xs"
                  onSelect={() => onSortChange(option.value)}
                >
                  <span className="flex-1 truncate">{option.label}</span>
                  {sortBy === option.value ? (
                    <Check className="size-3.5 text-muted-foreground" />
                  ) : null}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {activeFilterCount > 0 ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 px-2 text-xs text-muted-foreground"
              onClick={() => {
                onReset();
                resetPage();
              }}
            >
              {locale === "zh-CN" ? "重置" : "Reset"}
            </Button>
          ) : null}
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            onChange={(event) => {
              onSearchChange(event.target.value);
              resetPage();
            }}
            className="pl-8"
          />
        </div>
      </section>

      <SelectionActionBar
        locale={locale}
        count={selectedGroups.length}
        onClear={selection.clear}
      >
        <Button
          type="button"
          size="xs"
          variant="outline"
          disabled={Boolean(busyId)}
          onClick={() => {
            void onBulkEnabled(selectedGroups, true);
            selection.clear();
          }}
        >
          {locale === "zh-CN" ? "启动" : "Enable"}
        </Button>
        <Button
          type="button"
          size="xs"
          variant="outline"
          disabled={Boolean(busyId)}
          onClick={() => {
            void onBulkEnabled(selectedGroups, false);
            selection.clear();
          }}
        >
          {locale === "zh-CN" ? "停止" : "Disable"}
        </Button>
        {STRATEGY_OPTIONS.map((option) => (
          <Button
            key={option.value}
            type="button"
            size="xs"
            variant="outline"
            disabled={Boolean(busyId)}
            onClick={() => {
              void onBulkStrategy(selectedGroups, option.value);
              selection.clear();
            }}
          >
            <Shuffle className="size-3" />
            {locale === "zh-CN" ? option.zh : option.en}
          </Button>
        ))}
        <Button
          type="button"
          size="xs"
          variant="destructive"
          disabled={Boolean(busyId)}
          onClick={() => setBulkDeleteOpen(true)}
        >
          {locale === "zh-CN" ? "删除选中" : "Delete"}
        </Button>
      </SelectionActionBar>

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
          title={locale === "zh-CN" ? "合并模型组" : "Merge groups"}
          description={
            locale === "zh-CN"
              ? `将 ${mergeRequest?.source.name ?? ""} 的成员与引用合并至 ${mergeRequest?.target.name ?? ""}，并删除源模型组。`
              : `Move members and references from "${mergeRequest?.source.name ?? ""}" to "${mergeRequest?.target.name ?? ""}", then delete the source group.`
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
                onClick={async () => {
                  if (!mergeRequest) return;
                  if (await onMerge(mergeRequest.source, mergeRequest.target)) {
                    setMergeRequest(null);
                  }
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
        title={locale === "zh-CN" ? "删除模型组" : "Delete groups"}
        description={
          locale === "zh-CN"
            ? `删除选中的 ${selectedGroups.length} 个模型组。`
            : `Delete ${selectedGroups.length} selected groups.`
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
