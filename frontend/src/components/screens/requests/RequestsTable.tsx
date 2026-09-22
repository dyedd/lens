import { CornerDownRight } from "lucide-react";
import { useEffect, useState } from "react";
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
import { titleForLocale } from "@/lib/I18nContext";
import { protocolLabel } from "@/lib/protocols";
import { RequestOutcomeBadge } from "./RequestSummaryFields";
import {
  formatChannelCredentialLabel,
  formatGatewayKeyLabel,
  formatMaybeCount,
  formatMaybeMoney,
  formatMs,
  formatUserAgentDisplay,
  getResolvedGroupName,
  getSecondaryModelName,
} from "./requestView";

type Locale = "zh-CN" | "en-US";

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

function UsageChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex h-5 items-center justify-between gap-1 rounded-md bg-muted/35 px-1.5 font-mono text-[11px] leading-none text-muted-foreground">
      <span>{label}</span>
      <span className="tabular-nums">{value}</span>
    </span>
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
          label: "API Key",
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
              <CornerDownRight className="size-3 shrink-0 stroke-1" />
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
      <UsageChip
        label={titleForLocale(locale, "图片", "Images")}
        value={formatMaybeCount(item.billing_units, pending)}
      />
    );
  }
  const chips = [
    {
      label: titleForLocale(locale, "入", "in"),
      value: formatMaybeCount(item.input_tokens, pending),
    },
    {
      label: titleForLocale(locale, "出", "out"),
      value: formatMaybeCount(item.output_tokens, pending),
    },
    {
      label: titleForLocale(locale, "读", "cr"),
      value: formatMaybeCount(item.cache_read_input_tokens, pending),
    },
    {
      label: titleForLocale(locale, "写", "cw"),
      value: formatMaybeCount(item.cache_write_input_tokens, pending),
    },
  ];
  return (
    <div className="grid w-max max-w-[9.5rem] grid-cols-2 gap-1">
      {chips.map((chip) => (
        <UsageChip key={chip.label} label={chip.label} value={chip.value} />
      ))}
    </div>
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
            <span className="font-mono tabular-nums">
              {formatMaybeMoney(item.input_cost_usd, pending)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-5">
            <span>{titleForLocale(locale, "输出", "Output")}</span>
            <span className="font-mono tabular-nums">
              {formatMaybeMoney(item.output_cost_usd, pending)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-5 font-medium">
            <span>{titleForLocale(locale, "合计", "Total")}</span>
            <span className="font-mono tabular-nums">{value}</span>
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
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex cursor-default whitespace-nowrap font-mono tabular-nums text-muted-foreground">
          {formatMs(elapsedMs)}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="min-w-40">
        <div className="grid gap-1.5 text-xs">
          {item.billing_mode !== "non_tokens" ? (
            <div className="flex items-center justify-between gap-5">
              <span>{titleForLocale(locale, "首字", "First token")}</span>
              <span className="font-mono tabular-nums">
                {formatMs(item.first_token_latency_ms)}
              </span>
            </div>
          ) : null}
          <div className="flex items-center justify-between gap-5 font-medium">
            <span>{titleForLocale(locale, "总耗时", "Total")}</span>
            <span className="font-mono tabular-nums">
              {formatMs(elapsedMs)}
            </span>
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
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
