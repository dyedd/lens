import { useMemo } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
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
import type { HealthItem } from "@/lib/api/sites";
import { cn } from "@/lib/classNames";
import { titleForLocale } from "@/lib/I18nContext";
import {
  bucketTone,
  formatSuccessRate,
  type HealthMode,
  healthTierLabel,
  type Locale,
} from "./healthView";

type Props = {
  locale: Locale;
  mode: HealthMode;
  items: HealthItem[];
  loading: boolean;
  emptyLabel: string;
  timeZone: string;
  isResettingCooldown: boolean;
  onResetCooldown: (id: string) => void;
};

function HealthTimeline({
  item,
  locale,
  formatter,
}: {
  item: HealthItem;
  locale: Locale;
  formatter: Intl.DateTimeFormat;
}) {
  return (
    <div className="grid h-5 w-[18rem] min-w-[18rem] grid-cols-[repeat(60,minmax(0,1fr))] gap-px">
      {item.buckets.map((bucket) => {
        const startAt = formatter.format(new Date(bucket.started_at));
        const endAt = formatter.format(new Date(bucket.ended_at));
        const failureCount = Math.max(
          bucket.total_count - bucket.success_count,
          0,
        );
        const ariaLabel = titleForLocale(
          locale,
          `时间：${startAt} - ${endAt}，请求：${bucket.total_count}，失败：${failureCount}`,
          `Time: ${startAt} - ${endAt}, requests: ${bucket.total_count}, failures: ${failureCount}`,
        );
        return (
          <Tooltip key={bucket.started_at}>
            <TooltipTrigger asChild>
              <span
                role="img"
                className={cn("h-5 rounded-[1px]", bucketTone(bucket.tier))}
                aria-label={ariaLabel}
              />
            </TooltipTrigger>
            <TooltipContent
              side="top"
              sideOffset={6}
              className="grid min-w-36 gap-1.5"
            >
              <div className="font-medium">
                {titleForLocale(locale, "时间", "Time")}
              </div>
              <div className="text-background/80">
                {startAt} - {endAt}
              </div>
              <div className="grid gap-0.5 border-t border-background/20 pt-1.5">
                <div className="flex justify-between gap-4">
                  <span>{titleForLocale(locale, "请求", "Requests")}</span>
                  <span className="font-medium tabular-nums">
                    {bucket.total_count}
                  </span>
                </div>
                <div className="flex justify-between gap-4">
                  <span>{titleForLocale(locale, "失败", "Failures")}</span>
                  <span className="font-medium tabular-nums">
                    {failureCount}
                  </span>
                </div>
              </div>
            </TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}

/** Renders request-log health as a compact table. */
export function HealthTable({
  locale,
  mode,
  items,
  loading,
  emptyLabel,
  timeZone,
  isResettingCooldown,
  onResetCooldown,
}: Props) {
  const formatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        hour: "2-digit",
        minute: "2-digit",
        timeZone,
      }),
    [locale, timeZone],
  );

  return (
    <Table className="min-w-[880px]">
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-[16rem] min-w-[16rem] max-w-[16rem]">
            {mode === "model"
              ? titleForLocale(locale, "模型组", "Model group")
              : titleForLocale(locale, "渠道", "Channel")}
          </TableHead>
          <TableHead className="min-w-[88px]">
            {titleForLocale(locale, "状态", "Status")}
          </TableHead>
          <TableHead className="min-w-[88px]">
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  {titleForLocale(locale, "剩余冷却", "Cooldown left")}
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {titleForLocale(
                  locale,
                  "当前行内最长的剩余冷却时间。",
                  "The longest remaining cooldown in this row.",
                )}
              </TooltipContent>
            </Tooltip>
          </TableHead>
          <TableHead className="min-w-[88px]">
            {titleForLocale(locale, "成功率", "Success")}
          </TableHead>
          <TableHead className="min-w-[72px]">
            {titleForLocale(locale, "请求", "Requests")}
          </TableHead>
          <TableHead className="min-w-[18rem]">
            {titleForLocale(locale, "时间轴", "Timeline")}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {loading && items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={6}
              className="h-32 text-center text-muted-foreground"
            >
              {titleForLocale(locale, "加载中...", "Loading...")}
            </TableCell>
          </TableRow>
        ) : null}
        {!loading && items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={6}
              className="h-32 text-center text-muted-foreground"
            >
              {emptyLabel}
            </TableCell>
          </TableRow>
        ) : null}
        {items.map((item) => (
          <TableRow key={item.id} className="hover:bg-transparent">
            <TableCell className="w-[16rem] max-w-[16rem]">
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="block truncate font-medium">
                    {item.name}
                  </span>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-sm break-all">
                  {item.name}
                </TooltipContent>
              </Tooltip>
            </TableCell>
            <TableCell>
              <Badge
                variant="secondary"
                className="h-5 px-1.5 text-xs font-normal text-muted-foreground"
              >
                {healthTierLabel(item.tier, locale)}
              </Badge>
            </TableCell>
            <TableCell>
              {item.cooldown_remaining_seconds > 0 ? (
                <div className="flex items-center gap-2">
                  <span className="tabular-nums">
                    {titleForLocale(
                      locale,
                      `${item.cooldown_remaining_seconds} 秒`,
                      `${item.cooldown_remaining_seconds}s`,
                    )}
                  </span>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex">
                        <Button
                          type="button"
                          variant="ghost"
                          size="xs"
                          disabled={isResettingCooldown}
                          onClick={() => onResetCooldown(item.id)}
                          aria-label={titleForLocale(
                            locale,
                            `重置 ${item.name} 的冷却`,
                            `Reset cooldown for ${item.name}`,
                          )}
                        >
                          {titleForLocale(locale, "重置冷却", "Reset cooldown")}
                        </Button>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      {titleForLocale(
                        locale,
                        "共享 Key 或渠道的模型也会解除对应冷却。",
                        "Also clears the same cooldown for models sharing a key or channel.",
                      )}
                    </TooltipContent>
                  </Tooltip>
                </div>
              ) : (
                <span className="text-muted-foreground">-</span>
              )}
            </TableCell>
            <TableCell className="tabular-nums">
              {formatSuccessRate(item.success_count, item.total_count)}
            </TableCell>
            <TableCell className="tabular-nums text-muted-foreground">
              {item.total_count.toLocaleString()}
            </TableCell>
            <TableCell>
              <HealthTimeline
                item={item}
                locale={locale}
                formatter={formatter}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
