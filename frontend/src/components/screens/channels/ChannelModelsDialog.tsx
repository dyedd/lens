import {
  ArrowDownUp,
  Cable,
  Check,
  CloudDownload,
  Plus,
  Wand2,
} from "lucide-react";
import {
  type FormEventHandler,
  type ReactNode,
  useMemo,
  useState,
} from "react";
import { Button } from "@/components/ui/Button";
import { ConfirmDeleteDialog } from "@/components/ui/ConfirmDeleteDialog";
import {
  Dialog,
  DialogContent,
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
import { FilterPillGroup } from "@/components/ui/FilterPillGroup";
import { SelectionActionBar } from "@/components/ui/SelectionActionBar";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import { useRowSelection } from "@/hooks/useRowSelection";
import type { ProtocolKind } from "@/lib/api/protocols";
import { protocolLabel } from "@/lib/protocols";
import { ChannelModelPatternDialog } from "./ChannelModelPatternDialog";
import { ChannelModelsTable } from "./ChannelModelsTable";
import type {
  AggregatedModel,
  Locale,
  ModelStatusFilter,
} from "./channelTypes";
import { ProtocolDropdown } from "./ProtocolDropdown";

type ModelSort = "name-asc" | "name-desc" | "status-desc";

type Props = {
  children?: ReactNode;
  open: boolean;
  locale: Locale;
  channelName: string;
  supportsModelListing: boolean;
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
  detecting: boolean;
  onDetectProtocols: (keys: string[]) => Promise<void>;
  onOpenRemote: () => void;
  credentialOptions: Array<{ id: string; label: string }>;
  onApplyModelPattern: (
    credentialId: string,
    pattern: string,
    signal: AbortSignal,
  ) => Promise<boolean>;
  initialStatusFilter?: ModelStatusFilter;
};

/** Renders the model binding table for one channel. */
export function ChannelModelsDialog({
  children,
  open,
  onOpenChange,
  ...props
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        aria-describedby={undefined}
        className="flex max-h-[min(88vh,780px)] w-[calc(100vw-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-4xl"
      >
        <ChannelModelsBody onOpenChange={onOpenChange} {...props} />
        {children}
      </DialogContent>
    </Dialog>
  );
}

function ChannelModelsBody({
  locale,
  channelName,
  supportsModelListing,
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
  detecting,
  onDetectProtocols,
  onOpenRemote,
  credentialOptions,
  onApplyModelPattern,
  initialStatusFilter = "all",
}: Omit<Props, "open" | "children">) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] =
    useState<ModelStatusFilter>(initialStatusFilter);
  const [sortBy, setSortBy] = useState<ModelSort>("name-asc");
  const [newOpen, setNewOpen] = useState(false);
  const [bulkProtocols, setBulkProtocols] = useState<ProtocolKind[]>([
    "openai_chat",
  ]);
  const [removeRequest, setRemoveRequest] = useState<string[] | null>(null);

  const hasMultipleBaseUrls = useMemo(
    () => new Set(models.flatMap((model) => model.baseUrls)).size > 1,
    [models],
  );

  const visibleModels = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const filtered = models.filter((model) => {
      if (statusFilter === "enabled" && !model.enabled) return false;
      if (statusFilter === "disabled" && model.enabled) return false;
      if (!keyword) return true;
      return (
        model.modelName.toLowerCase().includes(keyword) ||
        model.protocols.some((protocol) =>
          protocolLabel(protocol, locale).toLowerCase().includes(keyword),
        ) ||
        (hasMultipleBaseUrls &&
          model.baseUrls.some((url) => url.toLowerCase().includes(keyword)))
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
      return left.modelName.localeCompare(right.modelName, locale);
    });
  }, [hasMultipleBaseUrls, locale, models, query, sortBy, statusFilter]);

  const selection = useRowSelection(visibleModels, modelKey);
  const selectedKeys = useMemo(
    () => selection.selectedRows.map(modelKey),
    [selection.selectedRows],
  );
  const selectedCount = selectedKeys.length;
  const sortOptions = modelSortOptions(locale);

  function applyBulkProtocols() {
    if (!bulkProtocols.length || selectedCount === 0) return;
    for (const key of selectedKeys) onUpdateProtocols(key, bulkProtocols);
  }

  function requestRemoval(keys: string[]) {
    if (!keys.length) return;
    setRemoveRequest(keys);
  }

  function confirmRemoval() {
    const keys = removeRequest ?? [];
    if (!keys.length) return;
    for (const key of keys) onDelete(key);
    selection.clear();
    setRemoveRequest(null);
  }

  return (
    <>
      <form
        className="flex min-h-0 flex-1 flex-col"
        onSubmit={(event) => {
          if (detecting) event.preventDefault();
          else onSave(event);
        }}
      >
        <DialogHeader className="shrink-0 px-5 pb-3 pt-5 pr-12">
          <DialogTitle>
            {locale === "zh-CN"
              ? `渠道模型 · ${channelName}`
              : `Models · ${channelName}`}
          </DialogTitle>
        </DialogHeader>

        <div className="flex shrink-0 flex-col gap-2.5 px-5 pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <FilterPillGroup
                value={statusFilter}
                ariaLabel={
                  locale === "zh-CN" ? "模型启用状态" : "Model status filter"
                }
                onValueChange={(value) =>
                  setStatusFilter(value as ModelStatusFilter)
                }
                options={[
                  {
                    value: "all",
                    label: locale === "zh-CN" ? "全部" : "All",
                  },
                  {
                    value: "enabled",
                    label: locale === "zh-CN" ? "已启用" : "Enabled",
                  },
                  {
                    value: "disabled",
                    label: locale === "zh-CN" ? "已停用" : "Paused",
                  },
                ]}
              />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 px-2 text-[13px] font-medium text-muted-foreground hover:text-foreground"
                    aria-label={locale === "zh-CN" ? "排序" : "Sort"}
                  >
                    <ArrowDownUp className="size-3.5" />
                    <span>
                      {sortOptions.find((o) => o.value === sortBy)?.label ??
                        (locale === "zh-CN" ? "排序" : "Sort")}
                    </span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="start"
                  className="z-[100] w-40 p-1.5"
                >
                  {sortOptions.map((option) => (
                    <DropdownMenuItem
                      key={option.value}
                      className="h-7 gap-2 px-2 py-0 text-xs"
                      onSelect={() => setSortBy(option.value)}
                    >
                      <span className="flex-1 truncate">{option.label}</span>
                      {sortBy === option.value ? (
                        <Check className="size-3.5 text-muted-foreground" />
                      ) : null}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            <div className="flex flex-1 flex-wrap items-center justify-end gap-2">
              <ToolbarSearchInput
                value={query}
                onChange={setQuery}
                onClear={() => setQuery("")}
                clearLabel={locale === "zh-CN" ? "清除搜索" : "Clear search"}
                placeholder={
                  hasMultipleBaseUrls
                    ? locale === "zh-CN"
                      ? "搜索模型名、地址或协议..."
                      : "Search model name, URL, or protocol..."
                    : locale === "zh-CN"
                      ? "搜索模型名或协议..."
                      : "Search model name or protocol..."
                }
                className="w-full sm:w-56"
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 shrink-0"
                disabled={fetching || detecting || !supportsModelListing}
                onClick={onOpenRemote}
              >
                <CloudDownload className="size-3.5" />
                {locale === "zh-CN" ? "获取模型列表" : "Fetch model list"}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 shrink-0"
                disabled={fetching || detecting}
                onClick={() => setNewOpen(true)}
              >
                <Plus className="size-3.5" />
                {locale === "zh-CN" ? "模型规则" : "Model rule"}
              </Button>
            </div>
          </div>

          <SelectionActionBar
            locale={locale}
            count={selectedCount}
            onClear={selection.clear}
          >
            <Button
              type="button"
              size="xs"
              variant="outline"
              onClick={() => {
                for (const key of selectedKeys) onToggleEnabled(key, true);
              }}
            >
              {locale === "zh-CN" ? "启用" : "Enable"}
            </Button>
            <Button
              type="button"
              size="xs"
              variant="outline"
              onClick={() => {
                for (const key of selectedKeys) onToggleEnabled(key, false);
              }}
            >
              {locale === "zh-CN" ? "停用" : "Disable"}
            </Button>
            <Button
              type="button"
              size="xs"
              variant="outline"
              disabled={detecting}
              onClick={() => void onDetectProtocols(selectedKeys)}
            >
              <Wand2 className="size-3" />
              {detecting
                ? locale === "zh-CN"
                  ? "识别中..."
                  : "Detecting..."
                : locale === "zh-CN"
                  ? "识别协议"
                  : "Detect"}
            </Button>
            <div className="flex items-center gap-1">
              <ProtocolDropdown
                value={bulkProtocols}
                locale={locale}
                className="h-7 min-h-7 w-32 px-2 py-0.5 text-xs"
                onChange={setBulkProtocols}
              />
              <Button
                type="button"
                size="xs"
                variant="outline"
                disabled={!bulkProtocols.length}
                onClick={applyBulkProtocols}
              >
                <Cable className="size-3" />
                {locale === "zh-CN" ? "应用协议" : "Apply"}
              </Button>
            </div>
            <Button
              type="button"
              size="xs"
              variant="destructive"
              onClick={() => requestRemoval(selectedKeys)}
            >
              {locale === "zh-CN" ? "删除" : "Delete"}
            </Button>
          </SelectionActionBar>
        </div>

        <div className="min-h-0 flex-1 overflow-hidden px-5 py-1">
          <ChannelModelsTable
            locale={locale}
            items={visibleModels}
            hasModels={models.length > 0}
            hasMultipleBaseUrls={hasMultipleBaseUrls}
            selected={selection.selected}
            testing={testing}
            detecting={detecting}
            onSelectAll={(checked) =>
              selection.toggleRows(visibleModels, checked)
            }
            onSelectOne={selection.toggleId}
            onToggleEnabled={onToggleEnabled}
            onUpdateProtocols={onUpdateProtocols}
            onDetectProtocols={onDetectProtocols}
            onUpdateContextWindow={onUpdateContextWindow}
            onDelete={(key) => requestRemoval([key])}
            onTest={onTest}
          />
        </div>
        <DialogFooter className="shrink-0 items-center justify-between gap-2 px-5 py-3">
          <span className="mr-auto font-mono text-xs tabular-nums text-muted-foreground">
            {locale === "zh-CN"
              ? `显示 ${visibleModels.length} / ${models.length} 个模型`
              : `Showing ${visibleModels.length} of ${models.length} models`}
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              {locale === "zh-CN" ? "关闭" : "Close"}
            </Button>
            <Button type="submit" size="sm" disabled={saving || detecting}>
              {saving
                ? locale === "zh-CN"
                  ? "保存中..."
                  : "Saving..."
                : detecting
                  ? locale === "zh-CN"
                    ? "后台识别中..."
                    : "Detecting in background..."
                  : locale === "zh-CN"
                    ? "保存"
                    : "Save"}
            </Button>
          </div>
        </DialogFooter>
      </form>
      <ChannelModelPatternDialog
        open={newOpen}
        locale={locale}
        onOpenChange={setNewOpen}
        onSubmit={onApplyModelPattern}
        credentialOptions={credentialOptions}
        supportsModelListing={supportsModelListing}
      />
      <ConfirmDeleteDialog
        open={removeRequest !== null}
        locale={locale}
        title={locale === "zh-CN" ? "删除模型" : "Delete models"}
        description={
          locale === "zh-CN"
            ? `删除 ${removeRequest?.length ?? 0} 个模型，保存后生效。`
            : `Remove ${removeRequest?.length ?? 0} models on save.`
        }
        onOpenChange={(open) => {
          if (!open) setRemoveRequest(null);
        }}
        onConfirm={confirmRemoval}
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
  ];
}
