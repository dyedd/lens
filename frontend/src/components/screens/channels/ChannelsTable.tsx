import { Pencil, Settings2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
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
  TruncatedTooltip,
} from "@/components/ui/Tooltip";
import type { Site } from "@/lib/api/sites";
import { siteEndpointUrls, siteModelCounts } from "./channelDisplay";
import type { Locale, SiteRow } from "./channelTypes";

const updatedAtOptions: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
};
function formatUpdatedAt(
  value: string | null | undefined,
  formatter: Intl.DateTimeFormat,
) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return formatter.format(date);
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
  onToggleEnabled,
  onDelete,
}: Props) {
  const updatedAtFormatter = new Intl.DateTimeFormat(locale, updatedAtOptions);
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
          <TableHead>
            {locale === "zh-CN" ? "渠道名称" : "Channel name"}
          </TableHead>
          <TableHead>{locale === "zh-CN" ? "接口地址" : "Base URL"}</TableHead>
          <TableHead className="text-center">
            {locale === "zh-CN" ? "状态" : "Status"}
          </TableHead>
          <TableHead>{locale === "zh-CN" ? "模型数" : "Models"}</TableHead>
          <TableHead>{locale === "zh-CN" ? "更新时间" : "Updated"}</TableHead>
          <TableHead className="w-[112px] text-right">
            {locale === "zh-CN" ? "操作" : "Actions"}
          </TableHead>
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
                {urls.length > 0 ? (
                  <TruncatedTooltip
                    content={urls[0]}
                    side="top"
                    contentClassName="max-w-sm break-all"
                  >
                    <div className="max-w-[14rem] truncate text-xs text-muted-foreground">
                      {urls[0]}
                    </div>
                  </TruncatedTooltip>
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
                <button
                  type="button"
                  onClick={() => onManageModels(site)}
                  className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs tabular-nums text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <Settings2 className="size-3.5" />
                  <span>
                    {models.enabled} / {models.total}
                  </span>
                </button>
              </TableCell>
              <TableCell className="whitespace-nowrap text-xs text-muted-foreground tabular-nums">
                {formatUpdatedAt(site.updated_at, updatedAtFormatter)}
              </TableCell>
              <TableCell className="w-[112px] py-1.5">
                <div className="intent-reveal flex h-7 items-center justify-end gap-0.5">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="text-muted-foreground shadow-none hover:text-foreground"
                        aria-label={
                          locale === "zh-CN" ? "管理模型" : "Manage models"
                        }
                        onClick={() => onManageModels(site)}
                      >
                        <Settings2 className="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      {locale === "zh-CN" ? "管理模型" : "Manage models"}
                    </TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="text-muted-foreground shadow-none hover:text-foreground"
                        aria-label={
                          locale === "zh-CN" ? "编辑渠道" : "Edit channel"
                        }
                        onClick={() => onEdit(site)}
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      {locale === "zh-CN" ? "编辑渠道" : "Edit channel"}
                    </TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        className="text-muted-foreground shadow-none hover:bg-destructive/10 hover:text-destructive"
                        aria-label={
                          locale === "zh-CN" ? "删除渠道" : "Delete channel"
                        }
                        onClick={() => onDelete(site)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      {locale === "zh-CN" ? "删除渠道" : "Delete channel"}
                    </TooltipContent>
                  </Tooltip>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
