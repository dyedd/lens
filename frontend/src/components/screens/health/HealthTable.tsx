import { useMemo } from "react";
import { Badge } from "@/components/ui/Badge";
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
              colSpan={5}
              className="h-32 text-center text-muted-foreground"
            >
              {titleForLocale(locale, "加载中...", "Loading...")}
            </TableCell>
          </TableRow>
        ) : null}
        {!loading && items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={5}
              className="h-32 text-center text-muted-foreground"
            >
              {emptyLabel}
            </TableCell>
          </TableRow>
        ) : null}
        {items.map((item) => (
          <TableRow key={item.name} className="hover:bg-transparent">
            <TableCell className="w-[16rem] max-w-[16rem]">
              <span className="block truncate font-medium" title={item.name}>
                {item.name}
              </span>
            </TableCell>
            <TableCell>
              <Badge
                variant="secondary"
                className="h-5 px-1.5 text-[11px] font-normal text-muted-foreground"
              >
                {healthTierLabel(item.tier, locale)}
              </Badge>
            </TableCell>
            <TableCell className="font-mono tabular-nums">
              {formatSuccessRate(item.success_count, item.total_count)}
            </TableCell>
            <TableCell className="font-mono tabular-nums text-muted-foreground">
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
