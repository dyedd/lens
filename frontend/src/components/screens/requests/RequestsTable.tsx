import { CornerDownRight } from "lucide-react";
import { useEffect, useState } from "react";
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
import type { RequestLogItem } from "@/lib/api/requests";
import { formatLogDateTime } from "@/lib/datetime";
import type { Locale } from "@/lib/I18nContext";
import { titleForLocale } from "@/lib/I18nContext";
import { protocolLabel } from "@/lib/protocols";
import { RequestOutcomeBadge } from "./RequestSummaryFields";
import {
  formatCacheHitRate,
  formatChannelCredentialLabel,
  formatGatewayKeyLabel,
  formatMaybeCount,
  formatMaybeMoney,
  formatMs,
  formatUserAgentDisplay,
  getResolvedGroupName,
  getSecondaryModelName,
} from "./requestView";

type Props = {
  locale: Locale;
  items: RequestLogItem[];
  loading: boolean;
  emptyLabel: string;
  timeZone: string;
  onOpenDetail: (id: number) => void;
};

function isRunning(item: RequestLogItem) {
  return (
    item.lifecycle_status === "connecting" ||
    item.lifecycle_status === "streaming"
  );
}

function ModelCell({ item, locale }: { item: RequestLogItem; locale: Locale }) {
  const name = getResolvedGroupName(item);
  const upstream = getSecondaryModelName(item);
  const display = item.reasoning_effort
    ? `${name} ${item.reasoning_effort}`
    : name;
  const lines = [
    {
      label: titleForLocale(locale, "模型组", "Group"),
      value: display,
    },
    upstream
      ? {
          label: titleForLocale(locale, "上游模型", "Upstream"),
          value: upstream,
        }
      : null,
    {
      label: titleForLocale(locale, "渠道", "Channel"),
      value: formatChannelCredentialLabel(item, locale),
    },
    item.gateway_key_id
      ? {
          label: titleForLocale(locale, "网关密钥", "Gateway key"),
          value: formatGatewayKeyLabel(item, locale),
        }
      : null,
    item.rate_multiplier === null
      ? null
      : {
          label: titleForLocale(locale, "倍率", "Rate"),
          value: `${item.rate_multiplier}x`,
        },
    {
      label: titleForLocale(locale, "协议", "Protocol"),
      value: protocolLabel(item.protocol, locale),
    },
    {
      label: titleForLocale(locale, "模式", "Mode"),
      value: item.is_stream
        ? titleForLocale(locale, "流式", "Stream")
        : titleForLocale(locale, "非流式", "Non-stream"),
    },
  ].filter((line): line is { label: string; value: string } => line !== null);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="grid w-[13rem] cursor-default gap-px">
          <div className="truncate font-medium leading-4">{display}</div>
          {upstream ? (
            <div className="flex min-w-0 items-center gap-1 font-mono leading-4 text-muted-foreground">
              <CornerDownRight className="size-3.5 shrink-0 stroke-1" />
              <span className="min-w-0 truncate">{upstream}</span>
            </div>
          ) : null}
        </div>
      </TooltipTrigger>
      <TooltipContent side="top">
        <div className="min-w-52 space-y-1 text-xs">
          {lines.map((line) => (
            <div
              key={line.label}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-8"
            >
              <span className="text-left">{line.label}</span>
              <span className="whitespace-nowrap text-right">{line.value}</span>
            </div>
          ))}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

function UsageCell({
  item,
  locale,
  pending,
}: {
  item: RequestLogItem;
  locale: Locale;
  pending: boolean;
}) {
  if (item.billing_mode === "non_tokens") {
    return (
      <Badge variant="secondary" className="gap-1 leading-none">
        <span>{titleForLocale(locale, "图片", "Images")}</span>
        <span className="tabular-nums">
          {formatMaybeCount(item.billing_units, pending)}
        </span>
      </Badge>
    );
  }

  return (
    <dl className="grid w-max grid-cols-[auto_auto_auto_auto] gap-x-3 gap-y-0.5 whitespace-nowrap text-xs leading-4">
      <dt className="text-muted-foreground">
        {titleForLocale(locale, "输入", "Input")}
      </dt>
      <dd className="text-right tabular-nums">
        {formatMaybeCount(item.input_tokens, pending)}
      </dd>
      <dt className="text-muted-foreground">
        {titleForLocale(locale, "输出", "Output")}
      </dt>
      <dd className="text-right tabular-nums">
        {formatMaybeCount(item.output_tokens, pending)}
      </dd>
      <dt className="text-muted-foreground">
        {titleForLocale(locale, "缓存读", "Cache read")}
      </dt>
      <dd className="text-right tabular-nums">
        {formatMaybeCount(item.cache_read_input_tokens, pending)}
      </dd>
      <dt className="text-muted-foreground">
        {titleForLocale(locale, "缓存写", "Cache write")}
      </dt>
      <dd className="text-right tabular-nums">
        {formatMaybeCount(item.cache_write_input_tokens, pending)}
      </dd>
      <dt className="col-span-3 text-muted-foreground">
        {titleForLocale(locale, "缓存命中率", "Cache hit rate")}
      </dt>
      <dd className="text-right tabular-nums">{formatCacheHitRate(item)}</dd>
    </dl>
  );
}

function CostCell({
  item,
  locale,
  pending,
}: {
  item: RequestLogItem;
  locale: Locale;
  pending: boolean;
}) {
  const value = formatMaybeMoney(item.total_cost_usd, pending);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex cursor-default font-medium tabular-nums">
          {value}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="min-w-40">
        <div className="grid gap-1.5 text-xs">
          <div className="flex items-center justify-between gap-5">
            <span>{titleForLocale(locale, "输入", "Input")}</span>
            <span className="tabular-nums">
              {formatMaybeMoney(item.input_cost_usd, pending)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-5">
            <span>{titleForLocale(locale, "输出", "Output")}</span>
            <span className="tabular-nums">
              {formatMaybeMoney(item.output_cost_usd, pending)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-5 font-medium">
            <span>{titleForLocale(locale, "合计", "Total")}</span>
            <span className="tabular-nums">{value}</span>
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

function LatencyCell({
  item,
  locale,
  elapsedMs,
}: {
  item: RequestLogItem;
  locale: Locale;
  elapsedMs: number;
}) {
  const hasTokenMetrics = item.billing_mode !== "non_tokens";
  // shortcut: 总耗时含重试等待，精确测速时需单独记录生成耗时。
  const outputMs = item.is_stream
    ? elapsedMs - item.first_token_latency_ms
    : elapsedMs;
  const outputTps =
    hasTokenMetrics &&
    !isRunning(item) &&
    (!item.is_stream || item.first_token_latency_ms > 0) &&
    item.output_tokens > 0 &&
    outputMs > 0
      ? `${((item.output_tokens * 1000) / outputMs).toFixed(1)} tok/s`
      : "-";

  return (
    <dl className="grid w-max grid-cols-[auto_auto] gap-x-3 gap-y-0.5 whitespace-nowrap text-xs leading-4">
      <dt className="text-muted-foreground">
        {titleForLocale(locale, "首字", "First token")}
      </dt>
      <dd className="text-right tabular-nums">
        {hasTokenMetrics && item.first_token_latency_ms > 0
          ? formatMs(item.first_token_latency_ms)
          : "-"}
      </dd>
      <dt className="text-muted-foreground">
        {titleForLocale(locale, "总耗时", "Total")}
      </dt>
      <dd className="text-right tabular-nums">{formatMs(elapsedMs)}</dd>
      <dt className="text-muted-foreground">
        {titleForLocale(locale, "输出 TPS", "Output TPS")}
      </dt>
      <dd className="text-right tabular-nums">{outputTps}</dd>
    </dl>
  );
}

/** Renders request logs as a compact table. */
export function RequestsTable({
  locale,
  items,
  loading,
  emptyLabel,
  timeZone,
  onOpenDetail,
}: Props) {
  const hasRunning = items.some(isRunning);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!hasRunning) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [hasRunning]);

  return (
    <Table className="min-w-[1080px]">
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="min-w-[72px] w-[72px]">ID</TableHead>
          <TableHead className="w-[13rem] min-w-[13rem] max-w-[13rem]">
            {titleForLocale(locale, "模型", "Model")}
          </TableHead>
          <TableHead className="min-w-[88px]">
            {titleForLocale(locale, "状态", "Status")}
          </TableHead>
          <TableHead className="min-w-[148px]">
            {titleForLocale(locale, "用量", "Usage")}
          </TableHead>
          <TableHead className="min-w-[96px]">
            {titleForLocale(locale, "费用", "Cost")}
          </TableHead>
          <TableHead className="min-w-[88px]">
            {titleForLocale(locale, "耗时", "Latency")}
          </TableHead>
          <TableHead className="min-w-[132px]">
            {titleForLocale(locale, "时间", "Time")}
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
              {titleForLocale(locale, "加载中...", "Loading...")}
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
        {items.map((item) => {
          const running = isRunning(item);
          const createdAtMs = new Date(item.created_at).getTime();
          const elapsedMs = running
            ? Math.max(now - createdAtMs, item.latency_ms || 0, 0)
            : item.latency_ms;
          return (
            <TableRow
              key={item.id}
              className="cursor-pointer"
              onClick={() => onOpenDetail(item.id)}
            >
              <TableCell className="font-mono text-xs text-foreground">
                {item.id}
              </TableCell>
              <TableCell className="w-[13rem] max-w-[13rem]">
                <ModelCell item={item} locale={locale} />
              </TableCell>
              <TableCell>
                <RequestOutcomeBadge
                  status={item.lifecycle_status}
                  statusCode={item.status_code}
                  locale={locale}
                  errorMessage={item.error_message}
                />
              </TableCell>
              <TableCell>
                <UsageCell item={item} locale={locale} pending={running} />
              </TableCell>
              <TableCell>
                <CostCell item={item} locale={locale} pending={running} />
              </TableCell>
              <TableCell>
                <LatencyCell
                  item={item}
                  locale={locale}
                  elapsedMs={elapsedMs}
                />
              </TableCell>
              <TableCell>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="inline-flex cursor-default whitespace-nowrap text-muted-foreground">
                      {formatLogDateTime(item.created_at, locale, timeZone)}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-sm">
                    {item.user_agent
                      ? formatUserAgentDisplay(item.user_agent, locale)
                      : titleForLocale(locale, "未知客户端", "Unknown client")}
                  </TooltipContent>
                </Tooltip>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
