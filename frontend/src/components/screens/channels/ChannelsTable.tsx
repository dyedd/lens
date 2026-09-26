import {
  CloudDownload,
  MoreHorizontal,
  Pencil,
  RefreshCw,
  Settings2,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { Site } from "@/lib/api/sites";
import { siteEndpointUrls, siteModelCounts } from "./channelModels";
import type { Locale, SiteRow } from "./channelTypes";

function formatUpdatedAt(value: string | null | undefined, locale: Locale) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

type Props = {
  locale: Locale;
  items: SiteRow[];
  loading: boolean;
  selected: Set<string>;
  busyId: string | null;
  onSelectAll: (checked: boolean) => void;
  onSelectOne: (id: string, checked: boolean) => void;
  onEdit: (site: Site) => void;
  onManageModels: (site: Site) => void;
  onReviewPendingModels: (site: Site) => void;
  onFetchModels: (site: Site) => void;
  syncingSiteId: string | null;
  onSyncModels: (site: Site) => void;
  onToggleEnabled: (site: Site, enabled: boolean) => void;
  onDelete: (site: Site) => void;
};

/** Renders the channel table. */
export function ChannelsTable({
  locale,
  items,
  loading,
  selected,
  busyId,
  onSelectAll,
  onSelectOne,
  onEdit,
  onManageModels,
  onReviewPendingModels,
  onFetchModels,
  syncingSiteId,
  onSyncModels,
  onToggleEnabled,
  onDelete,
}: Props) {
  const allSelected =
    items.length > 0 && items.every((item) => selected.has(item.id));
  const someSelected = items.some((item) => selected.has(item.id));
  const emptyLabel = locale === "zh-CN" ? "暂无渠道" : "No channels";
  const loadingLabel = locale === "zh-CN" ? "加载中..." : "Loading...";

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-[44px] text-center">
            <div className="flex h-7 items-center justify-center">
              <Checkbox
                checked={
                  allSelected ? true : someSelected ? "indeterminate" : false
                }
                onCheckedChange={(checked) => onSelectAll(checked === true)}
                aria-label={
                  locale === "zh-CN" ? "全选渠道" : "Select all channels"
                }
              />
            </div>
          </TableHead>
          <TableHead>{locale === "zh-CN" ? "名称" : "Name"}</TableHead>
          <TableHead>{locale === "zh-CN" ? "地址" : "URL"}</TableHead>
          <TableHead className="text-center">
            {locale === "zh-CN" ? "状态" : "Status"}
          </TableHead>
          <TableHead>{locale === "zh-CN" ? "模型数" : "Models"}</TableHead>
          <TableHead>{locale === "zh-CN" ? "更新时间" : "Updated"}</TableHead>
          <TableHead className="w-[56px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {loading && items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={7}
              className="h-32 text-center text-muted-foreground"
            >
              {loadingLabel}
            </TableCell>
          </TableRow>
        ) : null}
        {!loading && items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={7}
              className="h-32 text-center text-muted-foreground"
            >
              {emptyLabel}
            </TableCell>
          </TableRow>
        ) : null}
        {items.map((site) => {
          const urls = siteEndpointUrls(site);
          const models = siteModelCounts(site);
          const busy = busyId === site.id || busyId === "bulk";
          return (
            <TableRow
              key={site.id}
              data-state={selected.has(site.id) ? "selected" : undefined}
            >
              <TableCell className="w-[44px] py-1.5 text-center">
                <div className="flex h-7 items-center justify-center">
                  <Checkbox
                    checked={selected.has(site.id)}
                    onCheckedChange={(checked) =>
                      onSelectOne(site.id, checked === true)
                    }
                    aria-label={
                      locale === "zh-CN"
                        ? `选择 ${site.name}`
                        : `Select ${site.name}`
                    }
                  />
                </div>
              </TableCell>
              <TableCell>
                <div className="max-w-[18rem] truncate">
                  <span className="font-medium">{site.name}</span>
                </div>
              </TableCell>
              <TableCell>
                {urls.length === 1 ? (
                  <div
                    className="max-w-[14rem] truncate text-xs text-muted-foreground"
                    title={urls[0]}
                  >
                    {urls[0]}
                  </div>
                ) : urls.length > 1 ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Badge
                        variant="secondary"
                        className="cursor-default text-muted-foreground"
                      >
                        {locale === "zh-CN"
                          ? `${urls.length} 项`
                          : `${urls.length}`}
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      <div className="space-y-1">
                        {urls.map((url) => (
                          <div key={url} className="text-xs">
                            {url}
                          </div>
                        ))}
                      </div>
                    </TooltipContent>
                  </Tooltip>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {locale === "zh-CN" ? "未配置" : "Not set"}
                  </span>
                )}
              </TableCell>
              <TableCell className="py-1.5">
                <div className="flex h-7 items-center justify-center">
                  <Switch
                    size="sm"
                    checked={site.enabled}
                    disabled={busy}
                    onCheckedChange={(checked) =>
                      void onToggleEnabled(site, checked)
                    }
                    aria-label={
                      locale === "zh-CN"
                        ? `${site.enabled ? "停用" : "启用"} ${site.name}`
                        : `${site.enabled ? "Disable" : "Enable"} ${site.name}`
                    }
                  />
                </div>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="tabular-nums">
                    {locale === "zh-CN"
                      ? `活 ${models.enabled} / 总 ${models.total}`
                      : `${models.enabled} / ${models.total}`}
                  </span>
                  {models.pending ? (
                    <Badge variant="destructive" asChild>
                      <button
                        type="button"
                        className="cursor-pointer"
                        onClick={() => onReviewPendingModels(site)}
                        title={
                          locale === "zh-CN"
                            ? "上游已不再提供这些模型，点击确认保留或删除"
                            : "No longer listed upstream; review to keep or delete"
                        }
                      >
                        {locale === "zh-CN"
                          ? `${models.pending} 待确认`
                          : `${models.pending} to review`}
                      </button>
                    </Badge>
                  ) : null}
                </div>
              </TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">
                {formatUpdatedAt(site.updated_at, locale)}
              </TableCell>
              <TableCell className="w-[56px] py-1.5">
                <div className="flex h-7 items-center justify-end">
                  <DropdownMenu modal={false}>
                    <DropdownMenuTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="text-muted-foreground shadow-none"
                      >
                        <MoreHorizontal className="size-3.5 stroke-1" />
                        <span className="sr-only">
                          {locale === "zh-CN" ? "操作" : "Actions"}
                        </span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => onEdit(site)}>
                        <Pencil className="size-3.5 stroke-1" />
                        {locale === "zh-CN" ? "编辑渠道" : "Edit channel"}
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => onManageModels(site)}>
                        <Settings2 className="size-3.5 stroke-1" />
                        {locale === "zh-CN" ? "管理模型" : "Manage models"}
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => onFetchModels(site)}>
                        <CloudDownload className="size-3.5 stroke-1" />
                        {locale === "zh-CN" ? "获取模型" : "Fetch models"}
                      </DropdownMenuItem>
                      {site.model_sync_enabled ? (
                        <DropdownMenuItem
                          disabled={!site.enabled || syncingSiteId === site.id}
                          onSelect={() => onSyncModels(site)}
                        >
                          <RefreshCw className="size-3.5 stroke-1" />
                          {locale === "zh-CN" ? "立即同步" : "Sync now"}
                        </DropdownMenuItem>
                      ) : null}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onSelect={() => onDelete(site)}>
                        <Trash2 className="size-3.5 stroke-1" />
                        {locale === "zh-CN" ? "删除渠道" : "Delete channel"}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
