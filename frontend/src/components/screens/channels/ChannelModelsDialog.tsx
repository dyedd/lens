import {
  ArrowDownUp,
  Cable,
  Check,
  CloudDownload,
  Funnel,
  Plus,
} from "lucide-react";
import { type FormEventHandler, useMemo, useState } from "react";
import { BulkActionsPopover } from "@/components/ui/BulkActionsPopover";
import { Button } from "@/components/ui/Button";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
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
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import { useRowSelection } from "@/hooks/useRowSelection";
import type { ProtocolKind } from "@/lib/api/protocols";
import { protocolLabel, protocolOptions } from "@/lib/protocols";
import { AddChannelModelsDialog } from "./AddChannelModelsDialog";
import { ChannelModelsTable } from "./ChannelModelsTable";
import type {
  AggregatedModel,
  Locale,
  ModelStatusFilter,
} from "./channelTypes";
import { ProtocolDropdown } from "./ProtocolDropdown";

type ProtocolFilter = "all" | ProtocolKind;
type ModelSort = "name-asc" | "name-desc" | "status-desc" | "protocol-asc";

type Props = {
  open: boolean;
  locale: Locale;
  channelName: string;
  models: AggregatedModel[];
  saving: boolean;
  fetching: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: FormEventHandler<HTMLFormElement>;
  onToggleEnabled: (key: string, enabled: boolean) => void;
  onUpdateProtocols: (key: string, protocols: ProtocolKind[]) => void;
  onUpdateContextWindow: (key: string, contextWindow: number | null) => void;
  onDelete: (key: string) => void;
  onTest: (key: string) => void;
  testing: boolean;
  onAddBinding: (names: string, protocols: ProtocolKind[]) => boolean;
  onOpenRemote: () => void;
  initialStatusFilter?: ModelStatusFilter;
  isNested?: boolean;
};

/** Renders the model binding table for one channel. */
export function ChannelModelsDialog({ open, onOpenChange, ...props }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(86vh,760px)] w-[calc(100vw-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-4xl">
        <ChannelModelsBody onOpenChange={onOpenChange} {...props} />
      </DialogContent>
    </Dialog>
  );
}

function ChannelModelsBody({
  locale,
  channelName,
  models,
  saving,
  fetching,
  onOpenChange,
  onSave,
  onToggleEnabled,
  onUpdateProtocols,
  onUpdateContextWindow,
  onDelete,
  onTest,
  testing,
  onAddBinding,
  onOpenRemote,
  initialStatusFilter = "all",
  isNested = false,
}: Omit<Props, "open">) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] =
    useState<ModelStatusFilter>(initialStatusFilter);
  const [protocolFilter, setProtocolFilter] = useState<ProtocolFilter>("all");
  const [sortBy, setSortBy] = useState<ModelSort>("name-asc");
  const [newOpen, setNewOpen] = useState(false);
  const [bulkProtocols, setBulkProtocols] = useState<ProtocolKind[]>(["auto"]);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  const hasMultipleBaseUrls = useMemo(
    () => new Set(models.map((model) => model.baseUrl)).size > 1,
    [models],
  );

  const visibleModels = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const filtered = models.filter((model) => {
      if (statusFilter === "enabled" && !model.enabled) return false;
      if (statusFilter === "disabled" && model.enabled) return false;
      if (statusFilter === "missing" && !model.upstreamMissing) return false;
      if (
        protocolFilter !== "all" &&
        !model.protocols.includes(protocolFilter)
      ) {
        return false;
      }
      if (!keyword) return true;
      return (
        model.modelName.toLowerCase().includes(keyword) ||
        (hasMultipleBaseUrls &&
          model.baseUrl.toLowerCase().includes(keyword)) ||
        model.protocols.some((protocol) =>
          protocolLabel(protocol, locale).toLowerCase().includes(keyword),
        )
      );
    });
    return filtered.sort((left, right) => {
      if (sortBy === "name-desc") {
        return right.modelName.localeCompare(left.modelName, locale);
      }
      if (sortBy === "status-desc") {
        return (
          Number(right.enabled) - Number(left.enabled) ||
          left.modelName.localeCompare(right.modelName, locale)
        );
      }
      if (sortBy === "protocol-asc") {
        const leftLabel = left.protocols
          .map((protocol) => protocolLabel(protocol, locale))
          .join(",");
        const rightLabel = right.protocols
          .map((protocol) => protocolLabel(protocol, locale))
          .join(",");
        return (
          leftLabel.localeCompare(rightLabel, locale) ||
          left.modelName.localeCompare(right.modelName, locale)
        );
      }
      return left.modelName.localeCompare(right.modelName, locale);
    });
  }, [
    hasMultipleBaseUrls,
    locale,
    models,
    protocolFilter,
    query,
    sortBy,
    statusFilter,
  ]);

  const selection = useRowSelection(visibleModels, modelKey);
  const selectedKeys = useMemo(
    () => selection.selectedRows.map(modelKey),
    [selection.selectedRows],
  );
  const selectedCount = selectedKeys.length;
  const activeFilterCount =
    Number(statusFilter !== "all") + Number(protocolFilter !== "all");
  const sortOptions = modelSortOptions(locale);

  function applyBulkProtocols() {
    if (!bulkProtocols.length || selectedCount === 0) return;
    for (const key of selectedKeys) onUpdateProtocols(key, bulkProtocols);
  }

  function deleteSelected() {
    for (const key of selectedKeys) onDelete(key);
    selection.clear();
    setBulkDeleteOpen(false);
  }

  return (
    <>
      <form className="flex min-h-0 flex-1 flex-col" onSubmit={onSave}>
        <DialogHeader className="shrink-0 px-4 py-4">
          <DialogTitle>
            {locale === "zh-CN"
              ? `模型列表 - ${channelName}`
              : `Models - ${channelName}`}
          </DialogTitle>
          <DialogDescription>
            {locale === "zh-CN"
              ? "自动传递客户端协议；选择具体协议可将请求转换为该协议。"
              : "Auto passes the client protocol through. Choose a protocol to convert requests to it."}
            <span className="block">
              {locale === "zh-CN"
                ? "模型会按上游列表更新；删除模型后不会重新加入。上游已移除的模型会暂停调用。"
                : "Models follow the upstream list. Deleted models stay out; models removed upstream are paused."}
            </span>
          </DialogDescription>
        </DialogHeader>
        <div className="flex shrink-0 flex-nowrap items-center gap-1.5 overflow-x-auto px-4 pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <ToolbarSearchInput
            value={query}
            onChange={setQuery}
            onClear={() => setQuery("")}
            placeholder={
              hasMultipleBaseUrls
                ? locale === "zh-CN"
                  ? "搜索模型名、地址或协议..."
                  : "Search model name, URL, or protocol..."
                : locale === "zh-CN"
                  ? "搜索模型名或协议..."
                  : "Search model name or protocol..."
            }
            className="max-w-none min-w-40 flex-1"
          />
          <Popover modal={false}>
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
            <PopoverContent align="start" className="z-[100] w-[240px] p-2">
              <div className="space-y-2">
                <div className="space-y-1">
                  <p className="px-1 text-[10px] text-muted-foreground">
                    {locale === "zh-CN" ? "状态" : "Status"}
                  </p>
                  <Select
                    value={statusFilter}
                    onValueChange={(value) =>
                      setStatusFilter(value as ModelStatusFilter)
                    }
                  >
                    <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="z-[100]">
                      <SelectItem value="all">
                        {locale === "zh-CN" ? "全部状态" : "All statuses"}
                      </SelectItem>
                      <SelectItem value="enabled">
                        {locale === "zh-CN" ? "启用" : "Enabled"}
                      </SelectItem>
                      <SelectItem value="disabled">
                        {locale === "zh-CN" ? "停用" : "Disabled"}
                      </SelectItem>
                      <SelectItem value="missing">
                        {locale === "zh-CN" ? "待处理" : "Needs review"}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <p className="px-1 text-[10px] text-muted-foreground">
                    {locale === "zh-CN" ? "协议" : "Protocol"}
                  </p>
                  <Select
                    value={protocolFilter}
                    onValueChange={(value) =>
                      setProtocolFilter(value as ProtocolFilter)
                    }
                  >
                    <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="z-[100]">
                      <SelectItem value="all">
                        {locale === "zh-CN" ? "全部协议" : "All protocols"}
                      </SelectItem>
                      <SelectItem value="auto">
                        {protocolLabel("auto", locale)}
                      </SelectItem>
                      {protocolOptions(locale).map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {activeFilterCount ? (
                  <div className="flex justify-end border-t border-border/60 pt-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs shadow-none"
                      onClick={() => {
                        setStatusFilter("all");
                        setProtocolFilter("all");
                      }}
                    >
                      {locale === "zh-CN" ? "重置" : "Reset"}
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
            <DropdownMenuContent align="start" className="z-[100] w-40 p-1.5">
              {sortOptions.map((option) => (
                <DropdownMenuItem
                  key={option.value}
                  className="h-6 gap-2 px-2 py-0 text-[10px]"
                  onSelect={() => setSortBy(option.value)}
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
            count={selectedCount}
            isInDialog
            onSetEnabled={(enabled) => {
              for (const key of selectedKeys) onToggleEnabled(key, enabled);
            }}
            onDelete={() => setBulkDeleteOpen(true)}
          >
            <div className="mt-1 flex h-7 w-full items-center gap-1.5">
              <Button
                type="button"
                variant="ghost"
                className="h-7 w-16 shrink-0 justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted"
                disabled={!bulkProtocols.length}
                onClick={applyBulkProtocols}
              >
                <Cable className="size-3" />
                {locale === "zh-CN" ? "应用" : "Apply"}
              </Button>
              <ProtocolDropdown
                value={bulkProtocols}
                locale={locale}
                className="h-7 px-2 py-0 text-[11px] has-[>svg]:px-2"
                onChange={setBulkProtocols}
              />
            </div>
          </BulkActionsPopover>
          <div className="ml-auto flex shrink-0 items-center gap-1.5">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8"
              disabled={fetching}
              onClick={onOpenRemote}
            >
              <CloudDownload className="size-3.5" />
              {locale === "zh-CN" ? "获取模型列表" : "Fetch model list"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8"
              onClick={() => setNewOpen(true)}
            >
              <Plus className="size-3.5" />
              {locale === "zh-CN" ? "添加模型" : "Add models"}
            </Button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden px-4 py-2">
          <ChannelModelsTable
            locale={locale}
            items={visibleModels}
            hasModels={models.length > 0}
            hasMultipleBaseUrls={hasMultipleBaseUrls}
            selected={selection.selected}
            testing={testing}
            onSelectAll={(checked) =>
              selection.toggleRows(visibleModels, checked)
            }
            onSelectOne={selection.toggleId}
            onToggleEnabled={onToggleEnabled}
            onUpdateProtocols={onUpdateProtocols}
            onUpdateContextWindow={onUpdateContextWindow}
            onDelete={onDelete}
            onTest={onTest}
          />
        </div>
        <DialogFooter className="shrink-0 px-4 py-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            {isNested
              ? locale === "zh-CN"
                ? "返回"
                : "Back"
              : locale === "zh-CN"
                ? "关闭"
                : "Close"}
          </Button>
          <Button type="submit" size="sm" disabled={saving}>
            {saving
              ? locale === "zh-CN"
                ? "保存中..."
                : "Saving..."
              : locale === "zh-CN"
                ? "保存"
                : "Save"}
          </Button>
        </DialogFooter>
      </form>
      <AddChannelModelsDialog
        open={newOpen}
        locale={locale}
        onOpenChange={setNewOpen}
        onAddBinding={onAddBinding}
      />
      <ConfirmDeleteDialog
        open={bulkDeleteOpen}
        locale={locale}
        title={locale === "zh-CN" ? "删除模型" : "Delete models"}
        description={
          locale === "zh-CN"
            ? `删除选中的 ${selectedCount} 个模型及其同步目标，保存后生效。`
            : `${selectedCount} selected models and their sync targets will be removed after you save.`
        }
        isDisabled={selectedCount === 0}
        onOpenChange={setBulkDeleteOpen}
        onConfirm={deleteSelected}
      />
    </>
  );
}

const modelKey = (model: AggregatedModel) => model.key;

function modelSortOptions(
  locale: Locale,
): Array<{ value: ModelSort; label: string }> {
  return [
    {
      value: "name-asc",
      label: locale === "zh-CN" ? "名称升序" : "Name A-Z",
    },
    {
      value: "name-desc",
      label: locale === "zh-CN" ? "名称降序" : "Name Z-A",
    },
    {
      value: "status-desc",
      label: locale === "zh-CN" ? "启用优先" : "Enabled first",
    },
    {
      value: "protocol-asc",
      label: locale === "zh-CN" ? "协议升序" : "Protocol A-Z",
    },
  ];
}
