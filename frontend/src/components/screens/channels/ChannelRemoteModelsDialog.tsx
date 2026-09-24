import { CloudDownload, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import type { Locale, PickerModelItem } from "./channelTypes";

type Catalog = {
  items: PickerModelItem[];
  boundNames: Set<string>;
};

type Props = {
  open: boolean;
  locale: Locale;
  channelName: string;
  loading: boolean;
  onOpenChange: (open: boolean) => void;
  onLoad: () => Promise<Catalog | null>;
  onImport: (items: PickerModelItem[]) => number;
  autoSyncEnabled: boolean;
  autoSyncPattern: string;
  onAutoSyncChange: (enabled: boolean, pattern?: string) => void;
};

/** Renders the remote catalog preview for one channel. */
export function ChannelRemoteModelsDialog({
  open,
  locale,
  channelName,
  loading,
  onOpenChange,
  onLoad,
  onImport,
  autoSyncEnabled,
  autoSyncPattern,
  onAutoSyncChange,
}: Props) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState(false);
  const onLoadRef = useRef(onLoad);
  onLoadRef.current = onLoad;

  useEffect(() => {
    if (!open) {
      setCatalog(null);
      setQuery("");
      setSelected(new Set());
      return;
    }
    void onLoadRef.current().then((result) => {
      if (!result) return;
      setCatalog(result);
      setSelected(
        new Set(
          result.items
            .filter((item) => !result.boundNames.has(item.model_name))
            .map((item) => item.model_name),
        ),
      );
    });
  }, [open]);

  const uniqueItems = useMemo(() => {
    const byName = new Map<string, PickerModelItem>();
    for (const item of catalog?.items ?? []) {
      if (!byName.has(item.model_name)) byName.set(item.model_name, item);
    }
    return Array.from(byName.values());
  }, [catalog]);
  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return uniqueItems;
    return uniqueItems.filter((item) =>
      item.model_name.toLowerCase().includes(keyword),
    );
  }, [query, uniqueItems]);
  const unbound = filtered.filter(
    (item) => !catalog?.boundNames.has(item.model_name),
  );
  const allSelected =
    unbound.length > 0 &&
    unbound.every((item) => selected.has(item.model_name));
  const someSelected = unbound.some((item) => selected.has(item.model_name));

  function toggleAll(checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      for (const item of unbound) {
        if (checked) next.add(item.model_name);
        else next.delete(item.model_name);
      }
      return next;
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <AppDialogContent
        className="max-w-2xl"
        title={
          locale === "zh-CN"
            ? `同步上游模型 - ${channelName}`
            : `Sync upstream models - ${channelName}`
        }
        description={
          locale === "zh-CN"
            ? "拉取该渠道上游目录，勾选后把还没绑定的模型加进来。"
            : "Fetch this channel's upstream catalog, then add unbound models."
        }
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={importing}
            >
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={importing || loading || selected.size === 0}
              onClick={() => {
                const items = uniqueItems.filter((item) =>
                  selected.has(item.model_name),
                );
                setImporting(true);
                const count = onImport(items);
                toast.success(
                  locale === "zh-CN"
                    ? `已绑定 ${count || items.length} 个模型`
                    : `Bound ${count || items.length} models`,
                );
                setImporting(false);
                onOpenChange(false);
              }}
            >
              <CloudDownload className="size-3.5" />
              {locale === "zh-CN" ? "应用同步" : "Apply sync"}
            </Button>
          </>
        }
      >
        <div className="grid gap-3">
          <div className="rounded-md bg-muted/35 p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs font-medium">
                  {locale === "zh-CN"
                    ? "自动同步上游模型"
                    : "Auto-sync upstream models"}
                </div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  {locale === "zh-CN"
                    ? "定时任务会按上游目录更新同步模型"
                    : "Scheduled sync updates models from the upstream catalog"}
                </div>
              </div>
              <Switch
                size="sm"
                checked={autoSyncEnabled}
                onCheckedChange={(checked) => onAutoSyncChange(checked)}
              />
            </div>
            {autoSyncEnabled ? (
              <div className="mt-3">
                <Input
                  value={autoSyncPattern}
                  onChange={(event) =>
                    onAutoSyncChange(true, event.target.value)
                  }
                  placeholder={
                    locale === "zh-CN"
                      ? "模型筛选正则，可留空同步全部"
                      : "Optional model filter regex"
                  }
                  className="h-8 text-xs"
                  aria-label={
                    locale === "zh-CN" ? "模型筛选正则" : "Model filter regex"
                  }
                />
              </div>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <ToolbarSearchInput
              value={query}
              onChange={setQuery}
              onClear={() => setQuery("")}
              placeholder={
                locale === "zh-CN"
                  ? "搜索上游模型名"
                  : "Search upstream model names"
              }
              className="max-w-none flex-1"
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8"
              disabled={loading}
              onClick={() => {
                void onLoad().then((result) => {
                  if (result) setCatalog(result);
                });
              }}
            >
              <RefreshCw
                className={loading ? "size-3.5 animate-spin" : "size-3.5"}
              />
              {locale === "zh-CN" ? "重新拉取" : "Reload"}
            </Button>
          </div>
          <div className="text-xs text-muted-foreground">
            {loading
              ? locale === "zh-CN"
                ? "正在获取远端模型"
                : "Loading remote models"
              : locale === "zh-CN"
                ? `远端目录 ${uniqueItems.length} 个模型`
                : `${uniqueItems.length} models in the remote catalog`}
          </div>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[44px]">
                  <Checkbox
                    checked={
                      allSelected
                        ? true
                        : someSelected
                          ? "indeterminate"
                          : false
                    }
                    onCheckedChange={(checked) => toggleAll(checked === true)}
                  />
                </TableHead>
                <TableHead>
                  {locale === "zh-CN" ? "上游模型名" : "Upstream model"}
                </TableHead>
                <TableHead>{locale === "zh-CN" ? "状态" : "Status"}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell
                    colSpan={3}
                    className="h-24 text-center text-muted-foreground"
                  >
                    {loading
                      ? locale === "zh-CN"
                        ? "加载中..."
                        : "Loading..."
                      : locale === "zh-CN"
                        ? "暂无对应模型"
                        : "No models"}
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((item) => {
                  const bound = catalog?.boundNames.has(item.model_name);
                  return (
                    <TableRow key={item.model_name}>
                      <TableCell>
                        <Checkbox
                          checked={selected.has(item.model_name)}
                          disabled={bound}
                          onCheckedChange={(checked) => {
                            setSelected((current) => {
                              const next = new Set(current);
                              if (checked === true) next.add(item.model_name);
                              else next.delete(item.model_name);
                              return next;
                            });
                          }}
                        />
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {item.model_name}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {bound
                          ? locale === "zh-CN"
                            ? "已绑定"
                            : "Bound"
                          : locale === "zh-CN"
                            ? "未绑定"
                            : "Unbound"}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </AppDialogContent>
    </Dialog>
  );
}
