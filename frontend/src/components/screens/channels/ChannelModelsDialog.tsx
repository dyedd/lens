import {
  Activity,
  ArrowDownUp,
  Cable,
  Check,
  CloudDownload,
  Funnel,
  ListChecks,
  Pin,
  Plus,
  RefreshCw,
  ToggleLeft,
  Trash2,
} from "lucide-react";
import { type FormEventHandler, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import {
  AppDialogContent,
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
import { Field, FieldLabel } from "@/components/ui/Field";
import { Label } from "@/components/ui/Label";
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
import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { Textarea } from "@/components/ui/Textarea";
import { ToolbarButton } from "@/components/ui/ToolbarButton";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { ProtocolKind } from "@/lib/api/protocols";
import { protocolLabel, protocolOptions } from "@/lib/protocols";
import type { Locale } from "./channelTypes";
import { ProtocolDropdown } from "./ProtocolDropdown";
import type { AggregatedModel } from "./useChannelQueries";

export type ModelStatusFilter = "all" | "enabled" | "disabled" | "missing";
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
  onDelete: (key: string) => void;
  onTest: (key: string) => void;
  testing: boolean;
  onAddBinding: (names: string, protocols: ProtocolKind[]) => boolean;
  onOpenRemote: () => void;
  onKeep: (keys: string[]) => void;
  syncEnabled: boolean;
  syncing: boolean;
  onSyncNow: () => void;
  initialStatusFilter?: ModelStatusFilter;
  isNested?: boolean;
};

/** Renders the model binding table for one channel. */
export function ChannelModelsDialog({
  open,
  locale,
  channelName,
  models,
  saving,
  fetching,
  onOpenChange,
  onSave,
  onToggleEnabled,
  onUpdateProtocols,
  onDelete,
  onTest,
  testing,
  onAddBinding,
  onOpenRemote,
  onKeep,
  syncEnabled,
  syncing,
  onSyncNow,
  initialStatusFilter = "all",
  isNested = false,
}: Props) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] =
    useState<ModelStatusFilter>(initialStatusFilter);
  const [protocolFilter, setProtocolFilter] = useState<ProtocolFilter>("all");
  const [sortBy, setSortBy] = useState<ModelSort>("name-asc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [newOpen, setNewOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newProtocols, setNewProtocols] = useState<ProtocolKind[]>(["auto"]);
  const [bulkEnabled, setBulkEnabled] = useState<"enabled" | "disabled" | "">(
    "",
  );
  const [bulkProtocols, setBulkProtocols] = useState<ProtocolKind[]>(["auto"]);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);

  useEffect(() => {
    if (open) return;
    setQuery("");
    setStatusFilter("all");
    setProtocolFilter("all");
    setSortBy("name-asc");
    setSelected(new Set());
    setNewOpen(false);
    setNewName("");
    setNewProtocols(["auto"]);
    setBulkEnabled("");
    setBulkProtocols(["auto"]);
    setBulkDeleteOpen(false);
  }, [open]);

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
        model.protocols.some((protocol) =>
          protocolLabel(protocol, locale).toLowerCase().includes(keyword),
        )
      );
    });
    return [...filtered].sort((left, right) => {
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
  }, [locale, models, protocolFilter, query, sortBy, statusFilter]);

  const modelKeys = useMemo(
    () => new Set(visibleModels.map((model) => model.key)),
    [visibleModels],
  );
  const selectedKeys = useMemo(
    () => [...selected].filter((key) => modelKeys.has(key)),
    [modelKeys, selected],
  );
  const selectedCount = selectedKeys.length;
  const allSelected =
    visibleModels.length > 0 &&
    visibleModels.every((model) => selected.has(model.key));
  const someSelected = visibleModels.some((model) => selected.has(model.key));
  const activeFilterCount =
    Number(statusFilter !== "all") + Number(protocolFilter !== "all");
  const sortOptions: Array<{ value: ModelSort; label: string }> = [
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

  function handleSelectAll(checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const model of visibleModels) {
        if (checked) next.add(model.key);
        else next.delete(model.key);
      }
      return next;
    });
  }

  function handleSelectOne(key: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  function applyBulkEnabled() {
    if (!bulkEnabled || selectedCount === 0) return;
    const enabled = bulkEnabled === "enabled";
    for (const key of selectedKeys) onToggleEnabled(key, enabled);
  }

  function applyBulkProtocols() {
    if (!bulkProtocols.length || selectedCount === 0) return;
    for (const key of selectedKeys) onUpdateProtocols(key, bulkProtocols);
  }

  function deleteSelected() {
    for (const key of selectedKeys) onDelete(key);
    setSelected(new Set());
    setBulkDeleteOpen(false);
  }

  function keepSelected() {
    onKeep(selectedKeys);
    setSelected(new Set());
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex max-h-[min(86vh,760px)] w-[calc(100vw-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
          <form className="flex min-h-0 flex-1 flex-col" onSubmit={onSave}>
            <DialogHeader className="shrink-0 px-4 py-4">
              <DialogTitle>
                {locale === "zh-CN"
                  ? `管理模型 - ${channelName}`
                  : `Manage models - ${channelName}`}
              </DialogTitle>
              <DialogDescription>
                {syncEnabled
                  ? locale === "zh-CN"
                    ? "已开启自动同步：删除的同步模型会在下次同步时重新加入，停用即可排除；待确认的模型已暂停调用，可保留或删除。"
                    : "Auto-sync is on: deleted synced models return on the next sync, so disable them instead. Models to review are paused; keep or delete them."
                  : locale === "zh-CN"
                    ? "默认按客户端协议透传，也可指定上游协议进行转换。"
                    : "Forward the client protocol by default, or select an upstream protocol for conversion."}
              </DialogDescription>
            </DialogHeader>
            <div className="flex shrink-0 flex-nowrap items-center gap-1.5 overflow-x-auto px-4 pb-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <ToolbarSearchInput
                value={query}
                onChange={setQuery}
                onClear={() => setQuery("")}
                placeholder={
                  locale === "zh-CN"
                    ? "搜索模型名或协议"
                    : "Search model name or protocol"
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
                            {locale === "zh-CN" ? "待确认" : "To review"}
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
                          {locale === "zh-CN" ? "清空" : "Clear"}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </PopoverContent>
              </Popover>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <ToolbarButton
                    aria-label={locale === "zh-CN" ? "排序" : "Sort"}
                  >
                    <ArrowDownUp className="size-3.5" />
                    <span className="hidden sm:inline">
                      {locale === "zh-CN" ? "排序" : "Sort"}
                    </span>
                  </ToolbarButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="start"
                  className="z-[100] w-40 p-1.5"
                >
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
              <Popover modal={false}>
                <PopoverTrigger asChild>
                  <ToolbarButton
                    disabled={selectedCount === 0}
                    aria-label={locale === "zh-CN" ? "批量" : "Bulk"}
                  >
                    <ListChecks className="size-3.5" />
                    <span className="hidden sm:inline">
                      {locale === "zh-CN" ? "批量" : "Bulk"}
                    </span>
                  </ToolbarButton>
                </PopoverTrigger>
                <PopoverContent align="start" className="z-[100] w-[240px] p-2">
                  <p className="flex h-7 items-center px-2 text-[11px] text-muted-foreground">
                    {locale === "zh-CN"
                      ? `已选 ${selectedCount} 项`
                      : `${selectedCount} selected`}
                  </p>
                  <div className="flex h-7 w-full items-center gap-1.5">
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-7 w-16 shrink-0 justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted"
                      disabled={!bulkEnabled || selectedCount === 0}
                      onClick={applyBulkEnabled}
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
                      <SelectContent className="z-[100]">
                        <SelectItem value="enabled">
                          {locale === "zh-CN" ? "启用" : "Enable"}
                        </SelectItem>
                        <SelectItem value="disabled">
                          {locale === "zh-CN" ? "停用" : "Disable"}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="mt-1 flex h-7 w-full items-center gap-1.5">
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-7 w-16 shrink-0 justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted"
                      disabled={!bulkProtocols.length || selectedCount === 0}
                      onClick={applyBulkProtocols}
                    >
                      <Cable className="size-3" />
                      {locale === "zh-CN" ? "应用" : "Apply"}
                    </Button>
                    <ProtocolDropdown
                      value={bulkProtocols}
                      locale={locale}
                      disabled={selectedCount === 0}
                      className="h-7 px-2 py-0 text-[11px] has-[>svg]:px-2"
                      onChange={setBulkProtocols}
                    />
                  </div>
                  <button
                    type="button"
                    disabled={selectedCount === 0}
                    onClick={keepSelected}
                    className="mt-1 flex h-7 w-full items-center gap-2 rounded-md px-2 text-left text-[11px] text-foreground/70 hover:bg-muted hover:text-foreground disabled:opacity-50"
                  >
                    <Pin className="size-3.5" />
                    {locale === "zh-CN" ? "保留为手动模型" : "Keep as manual"}
                  </button>
                  <button
                    type="button"
                    disabled={selectedCount === 0}
                    onClick={() => setBulkDeleteOpen(true)}
                    className="mt-1 flex h-7 w-full items-center gap-2 rounded-md px-2 text-left text-[11px] text-foreground/70 hover:bg-muted hover:text-foreground disabled:opacity-50"
                  >
                    <Trash2 className="size-3.5" />
                    {locale === "zh-CN" ? "批量删除" : "Delete selected"}
                  </button>
                </PopoverContent>
              </Popover>
              <div className="ml-auto flex shrink-0 items-center gap-1.5">
                {syncEnabled ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-8"
                    disabled={syncing || saving}
                    onClick={onSyncNow}
                  >
                    <RefreshCw
                      className={syncing ? "size-3.5 animate-spin" : "size-3.5"}
                    />
                    {locale === "zh-CN" ? "立即同步" : "Sync now"}
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-8"
                  disabled={fetching}
                  onClick={onOpenRemote}
                >
                  <CloudDownload className="size-3.5" />
                  {locale === "zh-CN" ? "获取模型" : "Fetch models"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={() => setNewOpen(true)}
                >
                  <Plus className="size-3.5" />
                  {locale === "zh-CN" ? "手动添加" : "Add manually"}
                </Button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden px-4 py-2">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-[44px] text-center">
                      <div className="flex h-7 items-center justify-center">
                        <Checkbox
                          checked={
                            allSelected
                              ? true
                              : someSelected
                                ? "indeterminate"
                                : false
                          }
                          onCheckedChange={(checked) =>
                            handleSelectAll(checked === true)
                          }
                          aria-label={
                            locale === "zh-CN"
                              ? "全选模型"
                              : "Select all models"
                          }
                        />
                      </div>
                    </TableHead>
                    <TableHead className="w-[56px]">
                      {locale === "zh-CN" ? "状态" : "Status"}
                    </TableHead>
                    <TableHead>
                      {locale === "zh-CN" ? "上游模型名" : "Upstream model"}
                    </TableHead>
                    <TableHead className="w-[64px]">
                      {locale === "zh-CN" ? "来源" : "Source"}
                    </TableHead>
                    <TableHead className="w-[180px]">
                      {locale === "zh-CN" ? "转发方式" : "Forwarding"}
                    </TableHead>
                    <TableHead className="w-[72px]" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleModels.length === 0 ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell
                        colSpan={6}
                        className="h-28 text-center text-muted-foreground"
                      >
                        {models.length === 0
                          ? locale === "zh-CN"
                            ? "还没有模型。获取上游模型，或手动添加。"
                            : "No models yet. Fetch upstream models, or add them manually."
                          : locale === "zh-CN"
                            ? "没有匹配的模型。"
                            : "No matching models."}
                      </TableCell>
                    </TableRow>
                  ) : (
                    visibleModels.map((model) => (
                      <TableRow
                        key={model.key}
                        data-state={
                          selected.has(model.key) ? "selected" : undefined
                        }
                      >
                        <TableCell className="w-[44px] py-1.5 text-center">
                          <div className="flex h-7 items-center justify-center">
                            <Checkbox
                              checked={selected.has(model.key)}
                              onCheckedChange={(checked) =>
                                handleSelectOne(model.key, checked === true)
                              }
                              aria-label={
                                locale === "zh-CN"
                                  ? `选择 ${model.modelName}`
                                  : `Select ${model.modelName}`
                              }
                            />
                          </div>
                        </TableCell>
                        <TableCell className="py-1.5">
                          <div className="flex h-7 items-center">
                            <Switch
                              size="sm"
                              checked={model.enabled}
                              onCheckedChange={(checked) =>
                                onToggleEnabled(model.key, checked)
                              }
                            />
                          </div>
                        </TableCell>
                        <TableCell className="max-w-[220px] py-1.5 font-mono text-xs text-muted-foreground">
                          <div className="flex h-7 min-w-0 items-center gap-1.5">
                            <span className="truncate" title={model.modelName}>
                              {model.modelName}
                            </span>
                            {model.upstreamMissing ? (
                              <Badge
                                variant="destructive"
                                className="shrink-0 font-sans"
                                title={
                                  locale === "zh-CN"
                                    ? "上游已不再提供，暂停调用"
                                    : "No longer listed upstream; paused"
                                }
                              >
                                {locale === "zh-CN" ? "待确认" : "Review"}
                              </Badge>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="w-[64px] py-1.5 text-xs text-muted-foreground">
                          {model.source === "synced"
                            ? locale === "zh-CN"
                              ? "同步"
                              : "Synced"
                            : locale === "zh-CN"
                              ? "手动"
                              : "Manual"}
                        </TableCell>
                        <TableCell className="w-[180px] py-1.5">
                          <ProtocolDropdown
                            value={model.protocols}
                            locale={locale}
                            className="h-7 px-2 py-0 text-[11px] has-[>svg]:px-2"
                            onChange={(protocols) =>
                              onUpdateProtocols(model.key, protocols)
                            }
                          />
                        </TableCell>
                        <TableCell className="w-[72px] py-1.5">
                          <div className="flex h-7 items-center justify-end gap-0.5">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="inline-flex">
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon-sm"
                                    className="size-6 text-muted-foreground"
                                    disabled={testing || !model.testKey}
                                    aria-label={
                                      locale === "zh-CN"
                                        ? "测试模型"
                                        : "Test model"
                                    }
                                    onClick={() => {
                                      if (model.testKey) onTest(model.testKey);
                                    }}
                                  >
                                    <Activity className="size-3.5 stroke-1" />
                                  </Button>
                                </span>
                              </TooltipTrigger>
                              <TooltipContent side="top">
                                {model.testKey
                                  ? locale === "zh-CN"
                                    ? "测试"
                                    : "Test"
                                  : locale === "zh-CN"
                                    ? "无法测试"
                                    : "Cannot test"}
                              </TooltipContent>
                            </Tooltip>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              className="size-6 text-muted-foreground"
                              aria-label={
                                locale === "zh-CN"
                                  ? "删除绑定"
                                  : "Delete binding"
                              }
                              onClick={() => onDelete(model.key)}
                            >
                              <Trash2 className="size-3.5 stroke-1" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
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
        </DialogContent>
      </Dialog>
      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <AppDialogContent
          className="max-w-md"
          title={locale === "zh-CN" ? "手动添加模型" : "Add models manually"}
          description={
            locale === "zh-CN"
              ? "每行或用逗号分隔一个模型名，会加到所有密钥下。手动模型不受自动同步影响。"
              : "One model name per line or comma-separated, added for every key. Manual models are never changed by auto-sync."
          }
          footer={
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setNewOpen(false)}
              >
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={!newName.trim() || newProtocols.length === 0}
                onClick={() => {
                  if (onAddBinding(newName, newProtocols)) {
                    setNewName("");
                    setNewProtocols(["auto"]);
                    setNewOpen(false);
                  }
                }}
              >
                {locale === "zh-CN" ? "创建" : "Create"}
              </Button>
            </>
          }
        >
          <div className="grid gap-3">
            <div className="min-w-0 space-y-1">
              <Label
                required
                className="text-xs font-normal text-muted-foreground"
              >
                {locale === "zh-CN" ? "上游模型名" : "Upstream model names"}
              </Label>
              <Textarea
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
                placeholder={"gpt-4o\ngpt-4o-mini"}
                className="max-h-48 font-mono"
              />
            </div>
            <Field>
              <FieldLabel>
                {locale === "zh-CN" ? "转发方式" : "Forwarding"}
              </FieldLabel>
              <ProtocolDropdown
                value={newProtocols}
                locale={locale}
                onChange={setNewProtocols}
              />
            </Field>
          </div>
        </AppDialogContent>
      </Dialog>
      <Dialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AppDialogContent
          className="max-w-lg"
          showCloseButton={false}
          title={locale === "zh-CN" ? "确认批量删除" : "Delete models"}
          description={
            locale === "zh-CN"
              ? `将删除选中的 ${selectedCount} 个模型，保存后生效。${syncEnabled ? "上游仍提供的同步模型会在下次同步时重新加入。" : ""}`
              : `${selectedCount} selected models will be removed after you save.${syncEnabled ? " Synced models still listed upstream return on the next sync." : ""}`
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
                disabled={selectedCount === 0}
                onClick={deleteSelected}
              >
                {locale === "zh-CN" ? "确认删除" : "Delete"}
              </Button>
            </>
          }
        />
      </Dialog>
    </>
  );
}
