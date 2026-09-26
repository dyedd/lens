import { CloudDownload, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import { CredentialBadges } from "./CredentialBadges";
import { formatBaseUrlLabel } from "./channelModels";
import type { Locale, PickerModelItem } from "./channelTypes";
import type {
  RemoteModelCatalog,
  RemoteModelItem,
} from "./useChannelModelPicker";

type CatalogFilter = "new" | "bound" | "absent" | "all";
type CatalogRow = {
  name: string;
  status: Exclude<CatalogFilter, "all">;
  sources: RemoteModelItem[];
};

type Props = {
  open: boolean;
  locale: Locale;
  channelName: string;
  loading: boolean;
  onOpenChange: (open: boolean) => void;
  onLoad: () => Promise<RemoteModelCatalog | null>;
  onImport: (items: PickerModelItem[]) => number;
};

function statusLabel(status: CatalogRow["status"], locale: Locale) {
  if (status === "bound") return locale === "zh-CN" ? "已添加" : "Added";
  if (status === "absent") return locale === "zh-CN" ? "上游缺失" : "Missing";
  return locale === "zh-CN" ? "未添加" : "New";
}

/** Lets the admin pick upstream models across every URL and key. */
export function ChannelRemoteModelsDialog({
  open,
  locale,
  channelName,
  loading,
  onOpenChange,
  onLoad,
  onImport,
}: Props) {
  const [catalog, setCatalog] = useState<RemoteModelCatalog | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<CatalogFilter>("new");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const onLoadRef = useRef(onLoad);
  onLoadRef.current = onLoad;

  useEffect(() => {
    if (!open) {
      setCatalog(null);
      setQuery("");
      setFilter("new");
      setSelected(new Set());
      return;
    }
    void onLoadRef.current().then((result) => {
      if (result) setCatalog(result);
    });
  }, [open]);

  const rows = useMemo<CatalogRow[]>(() => {
    if (!catalog) return [];
    const sourcesByName = Map.groupBy(catalog.items, (item) => item.model_name);
    return [
      ...Array.from(sourcesByName, ([name, sources]) => ({
        name,
        status: catalog.boundNames.has(name) ? "bound" : "new",
        sources,
      })),
      ...Array.from(catalog.boundNames)
        .filter((name) => !sourcesByName.has(name))
        .map((name) => ({ name, status: "absent", sources: [] })),
    ] as CatalogRow[];
  }, [catalog]);
  const counts = useMemo(() => {
    const result = { new: 0, bound: 0, absent: 0, all: rows.length };
    for (const row of rows) result[row.status] += 1;
    return result;
  }, [rows]);
  const visibleRows = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return rows
      .filter(
        (row) =>
          (filter === "all" || row.status === filter) &&
          (!keyword || row.name.toLowerCase().includes(keyword)),
      )
      .sort((left, right) => left.name.localeCompare(right.name));
  }, [filter, query, rows]);
  const selectableNames = visibleRows
    .filter((row) => row.status === "new")
    .map((row) => row.name);
  const allSelected =
    selectableNames.length > 0 &&
    selectableNames.every((name) => selected.has(name));
  const someSelected = selectableNames.some((name) => selected.has(name));

  function toggleName(name: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(name);
      else next.delete(name);
      return next;
    });
  }

  function importSelected() {
    const items = (catalog?.items ?? []).filter((item) =>
      selected.has(item.model_name),
    );
    onImport(items);
    toast.success(
      locale === "zh-CN"
        ? `已添加 ${selected.size} 个模型，保存渠道后生效`
        : `Added ${selected.size} models. Save the channel to apply`,
    );
    onOpenChange(false);
  }

  const filterLabel = (zh: string, en: string, count: number) =>
    `${locale === "zh-CN" ? zh : en} ${count}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <AppDialogContent
        className="max-w-2xl"
        title={
          locale === "zh-CN"
            ? `获取上游模型 - ${channelName}`
            : `Fetch upstream models - ${channelName}`
        }
        description={
          locale === "zh-CN"
            ? "已汇总所有地址和密钥的模型列表。勾选的模型作为手动模型加入，不受自动同步影响。"
            : "Models from every URL and key. Picked models are added as manual models and never changed by auto-sync."
        }
        footer={
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              {locale === "zh-CN" ? "取消" : "Cancel"}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={loading || selected.size === 0}
              onClick={importSelected}
            >
              <CloudDownload className="size-3.5" />
              {locale === "zh-CN"
                ? `添加所选 ${selected.size}`
                : `Add selected ${selected.size}`}
            </Button>
          </>
        }
      >
        <div className="grid gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <SegmentedControl
              value={filter}
              onValueChange={setFilter}
              options={[
                {
                  value: "new",
                  label: filterLabel("未添加", "New", counts.new),
                },
                {
                  value: "bound",
                  label: filterLabel("已添加", "Added", counts.bound),
                },
                {
                  value: "absent",
                  label: filterLabel("上游缺失", "Missing", counts.absent),
                },
                { value: "all", label: filterLabel("全部", "All", counts.all) },
              ]}
            />
            <ToolbarSearchInput
              value={query}
              onChange={setQuery}
              onClear={() => setQuery("")}
              placeholder={
                locale === "zh-CN" ? "搜索模型名" : "Search model names"
              }
              className="max-w-none min-w-40 flex-1"
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
              {locale === "zh-CN" ? "重新获取" : "Reload"}
            </Button>
          </div>
          <div className="max-h-[min(52vh,480px)] overflow-y-auto">
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
                      disabled={!selectableNames.length}
                      onCheckedChange={(checked) =>
                        setSelected((current) => {
                          const next = new Set(current);
                          for (const name of selectableNames) {
                            if (checked === true) next.add(name);
                            else next.delete(name);
                          }
                          return next;
                        })
                      }
                      aria-label={
                        locale === "zh-CN"
                          ? "全选筛选结果"
                          : "Select filtered models"
                      }
                    />
                  </TableHead>
                  <TableHead>
                    {locale === "zh-CN" ? "上游模型名" : "Upstream model"}
                  </TableHead>
                  <TableHead className="w-[150px]">
                    {locale === "zh-CN" ? "密钥" : "Keys"}
                  </TableHead>
                  <TableHead className="w-[96px]">
                    {locale === "zh-CN" ? "状态" : "Status"}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleRows.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell
                      colSpan={4}
                      className="h-24 text-center text-muted-foreground"
                    >
                      {loading
                        ? locale === "zh-CN"
                          ? "正在获取上游模型..."
                          : "Fetching upstream models..."
                        : locale === "zh-CN"
                          ? "没有匹配的模型"
                          : "No matching models"}
                    </TableCell>
                  </TableRow>
                ) : (
                  visibleRows.map((row) => (
                    <TableRow key={row.name}>
                      <TableCell>
                        <Checkbox
                          checked={selected.has(row.name)}
                          disabled={row.status !== "new"}
                          onCheckedChange={(checked) =>
                            toggleName(row.name, checked === true)
                          }
                          aria-label={row.name}
                        />
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {row.name}
                      </TableCell>
                      <TableCell className="w-[150px] py-1.5">
                        <CredentialBadges
                          keys={[
                            ...new Map(
                              row.sources.map((source) => [
                                source.credential_id,
                                {
                                  id: source.credential_id,
                                  label: source.credentialName,
                                },
                              ]),
                            ).values(),
                          ]}
                          totalCount={catalog?.credentialCount ?? 0}
                          details={row.sources.map((source) =>
                            catalog?.hasMultipleBaseUrls
                              ? `${source.credentialTitle} · ${formatBaseUrlLabel(source.baseUrl)}`
                              : source.credentialTitle,
                          )}
                          locale={locale}
                        />
                      </TableCell>
                      <TableCell
                        className={
                          row.status === "absent"
                            ? "text-xs text-destructive"
                            : "text-xs text-muted-foreground"
                        }
                      >
                        {statusLabel(row.status, locale)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </AppDialogContent>
    </Dialog>
  );
}
