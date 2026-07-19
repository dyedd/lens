"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Clock3,
  Database,
  DollarSign,
  Fingerprint,
  KeyRound,
  ServerCog,
  Upload,
  Waypoints,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { RequestLogItem } from "@/lib/api";
import { formatLogDateTime } from "@/lib/datetime";
import { titleForLocale } from "@/lib/I18nContext";
import { ModelAvatar } from "@/lib/ModelIcons";
import { cn } from "@/lib/utils";
import {
  ProtocolBadge,
  RequestMeta,
  RequestMetric,
  RequestOutcomeBadge,
} from "./RequestSummaryFields";
import {
  formatChannelCredentialLabel,
  formatErrorDisplay,
  formatGatewayKeyLabel,
  formatMaybeCount,
  formatMaybeMoney,
  formatMs,
  formatUserAgentDisplay,
  getModelChain,
  getResolvedGroupName,
  getSecondaryModelName,
} from "./requestLogUtils";

export { AttemptChain } from "./RequestAttemptChain";

/** Render a request log summary card and its available actions. */
export function RequestCard({
  item,
  locale,
  timeZone,
  canOpenDetail,
  onOpenDetail,
  onOpenAttempts,
}: {
  item: RequestLogItem;
  locale: "zh-CN" | "en-US";
  timeZone?: string;
  canOpenDetail: boolean;
  onOpenDetail: () => void;
  onOpenAttempts: () => void;
}) {
  const primaryModelName = getResolvedGroupName(item);
  const modelChain = getModelChain(item);
  const modelDisplayName = item.reasoning_effort
    ? `${modelChain} ${item.reasoning_effort}`
    : modelChain;
  const secondaryModelName = getSecondaryModelName(item);
  const attemptCount = Number.isFinite(item.attempt_count)
    ? item.attempt_count
    : 0;
  const errorDisplay = formatErrorDisplay(item.error_message);
  const running =
    item.lifecycle_status === "connecting" ||
    item.lifecycle_status === "streaming";
  const [now, setNow] = useState(() => Date.now());
  const createdAtMs = useMemo(
    () => new Date(item.created_at).getTime(),
    [item.created_at],
  );

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);

  const elapsedMs = running
    ? Math.max(now - createdAtMs, item.latency_ms || 0, 0)
    : item.latency_ms;

  return (
    <Card
      className={cn(
        "rounded-2xl py-0 transition-colors",
        canOpenDetail ? "hover:bg-muted/20" : "",
        item.lifecycle_status === "failed"
          ? "border-destructive/25 bg-destructive/[0.015]"
          : "",
      )}
    >
      <div
        role={canOpenDetail ? "button" : undefined}
        tabIndex={canOpenDetail ? 0 : undefined}
        onClick={canOpenDetail ? onOpenDetail : undefined}
        onKeyDown={(event) => {
          if (!canOpenDetail) return;
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onOpenDetail();
          }
        }}
        className={cn(
          "grid w-full min-w-0 grid-cols-[minmax(0,1fr)] items-start gap-x-3.5 gap-y-3 px-4 py-4 sm:grid-cols-[56px_minmax(0,1fr)]",
          canOpenDetail
            ? "cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            : "cursor-default",
        )}
      >
        <div className="hidden size-12 items-center justify-center self-start rounded-2xl border bg-muted/40 sm:flex">
          <ModelAvatar name={primaryModelName} size={28} />
        </div>

        <div className="grid min-w-0 gap-3">
          <div className="grid gap-2.5">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <div className="min-w-0 max-w-full truncate text-[15px] font-semibold leading-6 text-foreground">
                {modelDisplayName}
              </div>
              <ProtocolBadge protocol={item.protocol} />
              <RequestOutcomeBadge
                status={item.lifecycle_status}
                success={item.success}
                statusCode={item.status_code}
                locale={locale}
                errorMessage={errorDisplay}
              />
              {attemptCount > 1 ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 rounded-full px-2.5 text-xs"
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenAttempts();
                  }}
                >
                  <Waypoints data-icon="inline-start" />
                  {titleForLocale(
                    locale,
                    `链路 ${attemptCount}`,
                    `Attempts ${attemptCount}`,
                  )}
                </Button>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <RequestMeta
                icon={<Clock3 size={13} />}
                value={formatLogDateTime(item.created_at, locale, timeZone)}
                className="pl-0"
              />
              <RequestMeta
                icon={<Waypoints size={13} />}
                value={formatChannelCredentialLabel(item, locale)}
              />
              {item.gateway_key_id && item.gateway_has_multiple_keys ? (
                <RequestMeta
                  icon={<KeyRound size={13} />}
                  value={formatGatewayKeyLabel(item, locale)}
                />
              ) : null}
              {item.user_agent ? (
                <RequestMeta
                  icon={<Fingerprint size={13} />}
                  value={formatUserAgentDisplay(item.user_agent, locale)}
                  tooltip={item.user_agent}
                  className="sm:max-w-[360px]"
                />
              ) : null}
              {secondaryModelName ? (
                <RequestMeta
                  icon={<ServerCog size={13} />}
                  value={secondaryModelName}
                />
              ) : null}
            </div>
          </div>

          <div className="grid w-full grid-cols-[repeat(auto-fit,minmax(126px,1fr))] gap-2">
            <RequestMetric
              icon={<Zap size={14} />}
              label={titleForLocale(locale, "首字延迟", "First token")}
              value={formatMs(item.first_token_latency_ms)}
            />
            <RequestMetric
              icon={<ServerCog size={14} />}
              label={titleForLocale(locale, "总耗时", "Total")}
              value={formatMs(elapsedMs)}
            />
            <RequestMetric
              icon={<ArrowDownToLine size={14} />}
              label={titleForLocale(locale, "输入", "Input")}
              value={formatMaybeCount(item.input_tokens, running)}
            />
            <RequestMetric
              icon={<ArrowUpFromLine size={14} />}
              label={titleForLocale(locale, "输出", "Output")}
              value={formatMaybeCount(item.output_tokens, running)}
            />
            <RequestMetric
              icon={<Database size={14} />}
              label={titleForLocale(locale, "缓存读取", "Cache Read")}
              value={formatMaybeCount(item.cache_read_input_tokens, running)}
            />
            <RequestMetric
              icon={<Upload size={14} />}
              label={titleForLocale(locale, "缓存写入", "Cache Write")}
              value={formatMaybeCount(item.cache_write_input_tokens, running)}
            />
            <RequestMetric
              icon={<DollarSign size={14} />}
              label={titleForLocale(locale, "费用", "Cost")}
              value={formatMaybeMoney(item.total_cost_usd, running)}
              valueClassName="whitespace-nowrap break-normal text-[12px]"
            />
          </div>
        </div>
      </div>
    </Card>
  );
}
