import {
  ArrowDownUp,
  Check,
  Funnel,
  ListChecks,
  Plus,
  RefreshCw,
  Search,
  ToggleLeft,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
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
import type { ModelGroup, RoutingStrategy } from "@/lib/api/groups";
import type { ProtocolKind } from "@/lib/api/protocols";
import { cn } from "@/lib/classNames";
import { GroupsTable } from "./GroupsTable";
import type { GroupRow, GroupSort } from "./groupTypes";

const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

type Props = {
  locale: "zh-CN" | "en-US";
  visibleGroups: GroupRow[];
  isLoading: boolean;
  search: string;
  strategyFilter: "all" | RoutingStrategy;
  sortBy: GroupSort;
  activeFilterCount: number;
  protocolOptions: Array<{ value: ProtocolKind; label: string }>;
  protocolFilter: "all" | ProtocolKind;
  busyId: string | null;
  testingModel: boolean;
  onSearchChange: (value: string) => void;
  onStrategyChange: (value: "all" | RoutingStrategy) => void;
  onSortChange: (value: GroupSort) => void;
  onProtocolChange: (value: "all" | ProtocolKind) => void;
  onReset: () => void;
  onRefresh: () => void;
  onCreate: () => void;
  onOpenEdit: (group: ModelGroup) => void;
  onToggleEnabled: (group: GroupRow, enabled: boolean) => void;
  onDelete: (group: ModelGroup) => void;
  onTest: (group: GroupRow) => void;
  onBulkEnabled: (groups: GroupRow[], enabled: boolean) => void;
  onBulkDelete: (groups: ModelGroup[]) => void;
};

/** Renders the model group list as a toolbar and table. */
export function GroupsOverview({
  locale,
  visibleGroups,
  isLoading,
  search,
  strategyFilter,
  sortBy,
  activeFilterCount,
  protocolOptions,
  protocolFilter,
  busyId,
  testingModel,
  onSearchChange,
  onStrategyChange,
  onSortChange,
  onProtocolChange,
  onReset,
  onRefresh,
  onCreate,
  onOpenEdit,
  onToggleEnabled,
  onDelete,
  onTest,
  onBulkEnabled,
  onBulkDelete,
}: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [bulkEnabled, setBulkEnabled] = useState<"enabled" | "disabled" | "">(
    "",
  );
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const pageCount = Math.max(1, Math.ceil(visibleGroups.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const pagedGroups = useMemo(
    () => visibleGroups.slice((safePage - 1) * pageSize, safePage * pageSize),
    [pageSize, safePage, visibleGroups],
  );
  const selectedGroups = visibleGroups.filter((group) =>
    selected.has(group.id),
  );
  const sortOptions: Array<{ value: GroupSort; label: string }> = [
    {
      value: "members-desc",
      label: locale === "zh-CN" ? "成员优先" : "Members first",
    },
    {
      value: "enabled-desc",
      label: locale === "zh-CN" ? "启用优先" : "Enabled first",
    },
    {
      value: "name-asc",
      label: locale === "zh-CN" ? "名称升序" : "Name A-Z",
    },
    {
      value: "name-desc",
      label: locale === "zh-CN" ? "名称降序" : "Name Z-A",
    },
  ];
  function handleSelectAll(checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const group of pagedGroups) {
        if (checked) next.add(group.id);
        else next.delete(group.id);
      }
      return next;
    });
  }

  function handleSelectOne(id: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function handlePageSizeChange(size: number) {
    setPageSize(size);
    setPage(1);
  }

  return (
    <div className="space-y-3 pb-10">
      <div className="flex min-h-10 items-center justify-between gap-3 px-1">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">
            {locale === "zh-CN" ? "模型组管理" : "Model groups"}
          </h3>
          <p className="text-xs text-muted-foreground">
            {locale === "zh-CN"
              ? "渠道里的模型已可按原名直接调用；模型组用于起别名、合并多个模型名或自定义顺序，同名时模型组优先。"
              : "Channel models are callable by their own names. Use groups to alias, merge names, or set a custom order; a group wins over a same-named model."}
          </p>
        </div>
      </div>

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
                setPage(1);
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
                      setPage(1);
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
                {protocolOptions.length ? (
                  <div className="space-y-1">
                    <p className="px-1 text-[10px] text-muted-foreground">
                      {locale === "zh-CN" ? "协议" : "Protocol"}
                    </p>
                    <Select
                      value={protocolFilter}
                      onValueChange={(value) => {
                        onProtocolChange(value as "all" | ProtocolKind);
                        setPage(1);
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
                        setPage(1);
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

          <Popover>
            <PopoverTrigger asChild>
              <ToolbarButton
                disabled={selectedGroups.length === 0 || Boolean(busyId)}
                aria-label={locale === "zh-CN" ? "批量" : "Bulk"}
              >
                <ListChecks className="size-3.5" />
                <span className="hidden sm:inline">
                  {locale === "zh-CN" ? "批量" : "Bulk"}
                </span>
              </ToolbarButton>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-[240px] p-2">
              <p className="flex h-7 items-center px-2 text-[11px] text-muted-foreground">
                {locale === "zh-CN"
                  ? `已选 ${selectedGroups.length} 项`
                  : `${selectedGroups.length} selected`}
              </p>
              <div className="flex h-7 w-full items-center gap-1.5">
                <Button
                  type="button"
                  variant="ghost"
                  className="h-7 w-16 shrink-0 justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted"
                  disabled={!bulkEnabled || Boolean(busyId)}
                  onClick={() => {
                    void onBulkEnabled(
                      selectedGroups,
                      bulkEnabled === "enabled",
                    );
                    setSelected(new Set());
                  }}
                >
                  <ToggleLeft className="size-3" />
                  {locale === "zh-CN" ? "应用" : "Apply"}
                </Button>
                <Select
                  value={bulkEnabled || undefined}
                  onValueChange={(value) =>
                    setBulkEnabled(value as "enabled" | "disabled")
                  }
                >
                  <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                    <SelectValue
                      placeholder={locale === "zh-CN" ? "状态" : "Status"}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="enabled">
                      {locale === "zh-CN" ? "启动" : "Enable"}
                    </SelectItem>
                    <SelectItem value="disabled">
                      {locale === "zh-CN" ? "停止" : "Disable"}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <button
                type="button"
                disabled={Boolean(busyId)}
                onClick={() => setBulkDeleteOpen(true)}
                className="mt-1 flex h-7 w-full items-center gap-2 rounded-md px-2 text-left text-[11px] text-foreground/70 hover:bg-muted hover:text-foreground disabled:opacity-50"
              >
                <Trash2 className="size-3.5" />
                {locale === "zh-CN" ? "批量删除" : "Delete selected"}
              </button>
            </PopoverContent>
          </Popover>
        </div>

        <div className="ml-auto flex min-h-8 shrink-0 items-center gap-1">
          <ToolbarButton
            onClick={onRefresh}
            disabled={isLoading}
            aria-label={locale === "zh-CN" ? "刷新" : "Refresh"}
            title={locale === "zh-CN" ? "刷新" : "Refresh"}
          >
            <RefreshCw
              className={cn("size-3.5", isLoading && "animate-spin")}
            />
          </ToolbarButton>
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
        selected={selected}
        busyId={busyId}
        testingModel={testingModel}
        onSelectAll={handleSelectAll}
        onSelectOne={handleSelectOne}
        onEdit={onOpenEdit}
        onToggleEnabled={onToggleEnabled}
        onDelete={onDelete}
        onTest={onTest}
      />

      <TablePagination
        locale={locale}
        total={visibleGroups.length}
        page={safePage}
        pageCount={pageCount}
        pageSize={pageSize}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        onPageChange={setPage}
        onPageSizeChange={handlePageSizeChange}
      />

      <Dialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AppDialogContent
          className="max-w-lg"
          showCloseButton={false}
          title={locale === "zh-CN" ? "确认批量删除" : "Delete groups"}
          description={
            locale === "zh-CN"
              ? `将删除选中的 ${selectedGroups.length} 个模型组。`
              : `${selectedGroups.length} selected groups will be removed.`
          }
          footer={
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setBulkDeleteOpen(false)}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={Boolean(busyId)}
                onClick={() => {
                  void onBulkDelete(selectedGroups);
                  setSelected(new Set());
                  setBulkDeleteOpen(false);
                }}
              >
                {locale === "zh-CN" ? "确认删除" : "Delete"}
              </Button>
            </>
          }
        />
      </Dialog>
    </div>
  );
}
