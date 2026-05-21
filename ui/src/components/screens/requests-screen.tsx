"use client";

import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Clock3,
  DollarSign,
  Filter,
  ServerCog,
  Waypoints,
  Zap,
} from "lucide-react";
import { RequestLogDetail, RequestLogItem, apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { ModelAvatar } from "@/lib/model-icons";
import { Dialog, AppDialogContent } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function formatMs(value: number) {
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

function formatMoney(value: number) {
  return `$${value.toFixed(6)}`;
}

function formatCount(value: number) {
  return value.toLocaleString();
}

function formatDate(value: string, locale: "zh-CN" | "en-US") {
  return new Date(value).toLocaleString(
    locale === "zh-CN" ? "zh-CN" : "en-US",
    {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    },
  );
}

function JsonPanel({
  content,
  emptyText,
}: {
  content?: string | null;
  emptyText: string;
}) {
  if (!content) {
    return (
      <div className="px-4 py-4 text-xs text-muted-foreground">{emptyText}</div>
    );
  }

  let formatted = content;
  try {
    formatted = JSON.stringify(JSON.parse(content), null, 2);
  } catch {
    formatted = content;
  }

  return (
    <pre className="max-h-[440px] overflow-auto px-4 py-4 text-xs leading-6 text-foreground">
      {formatted}
    </pre>
  );
}

function MetricPill({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="inline-flex min-h-8 items-center gap-2 text-xs text-muted-foreground">
      <span className="inline-flex size-4.5 items-center justify-center">
        {icon}
      </span>
      <span className="truncate">
        {label} {value}
      </span>
    </div>
  );
}

function DetailStat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <Card className="py-0 shadow-none">
      <CardContent className="px-5 py-4">
        <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </div>
        <div
          className={cn(
            "mt-2.5 text-base font-semibold",
            accent ? "text-primary" : "text-foreground",
          )}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function StatusBadge({
  success,
  locale,
}: {
  success: boolean;
  locale: "zh-CN" | "en-US";
}) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-full border-0 px-3 py-1 text-xs font-medium",
        success
          ? "bg-primary/10 text-primary"
          : "bg-destructive/12 text-destructive",
      )}
    >
      {success
        ? locale === "zh-CN"
          ? "成功"
          : "Success"
        : locale === "zh-CN"
          ? "失败"
          : "Failed"}
    </Badge>
  );
}

function ProtocolBadge({ protocol }: { protocol: RequestLogItem["protocol"] }) {
  const labelMap = {
    openai_chat: "chat",
    openai_responses: "responses",
    openai_embedding: "embedding",
    anthropic: "anthropic",
    gemini: "gemini",
  } as const;

  return (
    <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-medium">
      {labelMap[protocol]}
    </Badge>
  );
}

function AttemptChain({
  detail,
  locale,
}: {
  detail: RequestLogDetail;
  locale: "zh-CN" | "en-US";
}) {
  const attempts = detail.attempts.length
    ? detail.attempts
    : [
        {
          channel_id: detail.channel_id || "n/a",
          channel_name: detail.channel_name || detail.channel_id || "n/a",
          model_name:
            detail.upstream_model_name ||
            detail.resolved_group_name ||
            detail.requested_group_name ||
            null,
          status_code: detail.status_code,
          success: detail.success,
          duration_ms: detail.latency_ms,
          error_message: detail.error_message || null,
        },
      ];

  return (
    <div className="grid gap-3">
      {attempts.map((attempt, index) => (
        <Card
          key={`${attempt.channel_id}-${index}`}
          className="py-0 shadow-none"
        >
          <CardContent className="px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full bg-muted px-2 text-xs font-semibold text-muted-foreground">
                  {index + 1}
                </span>
                <span className="max-w-[220px] truncate text-sm font-medium text-foreground">
                  {attempt.channel_name}
                </span>
                {attempt.model_name ? (
                  <span className="max-w-[220px] truncate text-xs text-muted-foreground">
                    {attempt.model_name}
                  </span>
                ) : null}
                <StatusBadge success={attempt.success} locale={locale} />
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{attempt.status_code ?? "-"}</span>
                <span>{formatMs(attempt.duration_ms)}</span>
              </div>
            </div>
            {attempt.error_message ? (
              <div className="mt-3 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
                {attempt.error_message}
              </div>
            ) : null}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function RequestCard({
  item,
  locale,
  onToggle,
}: {
  item: RequestLogItem;
  locale: "zh-CN" | "en-US";
  onToggle: () => void;
}) {
  const modelName =
    item.upstream_model_name ||
    item.resolved_group_name ||
    item.requested_group_name ||
    "";

  return (
    <Card
      className={cn(
        "overflow-hidden py-0 transition-colors hover:bg-muted/20",
        item.success ? "" : "border-destructive/25",
      )}
    >
      <Button
        type="button"
        variant="ghost"
        onClick={onToggle}
        className="h-auto w-full justify-start rounded-none px-0 py-0 text-left hover:bg-transparent"
      >
        <CardContent className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 px-5 py-5 lg:px-6">
          <div className="row-span-2 flex size-12 shrink-0 items-center justify-center self-start rounded-lg border bg-muted/40">
            <ModelAvatar name={modelName} size={28} />
          </div>

          <div className="min-w-0 self-center">
            <div className="flex flex-wrap items-center gap-2 text-sm leading-none">
              <span className="max-w-[220px] truncate font-semibold text-foreground">
                {item.requested_group_name || item.resolved_group_name || "n/a"}
              </span>
              <ProtocolBadge protocol={item.protocol} />
              <StatusBadge success={item.success} locale={locale} />
              {item.upstream_model_name &&
              item.upstream_model_name !== item.requested_group_name ? (
                <span className="max-w-[220px] truncate text-xs text-muted-foreground">
                  {item.upstream_model_name}
                </span>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 self-center pt-0.5">
            <MetricPill
              icon={<Clock3 size={14} />}
              label=""
              value={formatDate(item.created_at, locale)}
            />
            <MetricPill
              icon={<Waypoints size={14} />}
              label=""
              value={item.channel_name || item.channel_id || "n/a"}
            />
            <MetricPill
              icon={<Zap size={14} />}
              label={locale === "zh-CN" ? "首字" : "First"}
              value={formatMs(item.first_token_latency_ms)}
            />
            <MetricPill
              icon={<ServerCog size={14} />}
              label={locale === "zh-CN" ? "总耗时" : "Total"}
              value={formatMs(item.latency_ms)}
            />
            <MetricPill
              icon={<ArrowDownToLine size={14} />}
              label={locale === "zh-CN" ? "输入" : "Input"}
              value={formatCount(item.input_tokens)}
            />
            <MetricPill
              icon={<ArrowUpFromLine size={14} />}
              label={locale === "zh-CN" ? "输出" : "Output"}
              value={formatCount(item.output_tokens)}
            />
            <MetricPill
              icon={<DollarSign size={14} />}
              label={locale === "zh-CN" ? "费用" : "Cost"}
              value={formatMoney(item.total_cost_usd)}
            />
          </div>
        </CardContent>
      </Button>
    </Card>
  );
}

export function RequestsScreen() {
  const { locale } = useI18n();
  const [showFailedOnly, setShowFailedOnly] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["request-logs"],
    queryFn: () => apiRequest<RequestLogItem[]>("/admin/request-logs"),
    refetchInterval: 5000,
  });

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ["request-log-detail", detailId],
    queryFn: () =>
      apiRequest<RequestLogDetail>(`/admin/request-logs/${detailId}`),
    enabled: detailId !== null,
  });

  const visibleData = useMemo(() => {
    const list = data ?? [];
    return showFailedOnly ? list.filter((item) => !item.success) : list;
  }, [data, showFailedOnly]);

  const failedCount = useMemo(
    () => (data ?? []).filter((item) => !item.success).length,
    [data],
  );

  return (
    <section className="flex flex-col gap-4 md:gap-6">
      {typeof document !== "undefined" &&
      document.getElementById("header-portal")
        ? createPortal(
            <div className="flex flex-1 items-center justify-end gap-2">
              <Button
                variant={showFailedOnly ? "destructive" : "outline"}
                className={cn(
                  showFailedOnly
                    ? "bg-destructive/12 text-destructive hover:bg-destructive/18"
                    : "",
                )}
                type="button"
                onClick={() => setShowFailedOnly((current) => !current)}
              >
                <Filter data-icon="inline-start" />
                {locale === "zh-CN"
                  ? `仅看失败 ${failedCount ? `(${failedCount})` : ""}`
                  : `Failed only${failedCount ? ` (${failedCount})` : ""}`}
              </Button>
            </div>,
            document.getElementById("header-portal")!,
          )
        : null}

      <div className="grid gap-4">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">
            {locale === "zh-CN"
              ? "正在加载请求日志..."
              : "Loading request logs..."}
          </p>
        ) : null}

        {!isLoading && visibleData.length === 0 ? (
          <Card className="border-dashed py-0 shadow-none">
            <CardContent className="px-6 py-14 text-center text-sm text-muted-foreground">
              {locale === "zh-CN" ? "暂无请求日志。" : "No request logs yet."}
            </CardContent>
          </Card>
        ) : null}

        {visibleData.map((item) => (
          <RequestCard
            key={item.id}
            item={item}
            locale={locale}
            onToggle={() => setDetailId(item.id)}
          />
        ))}
      </div>

      <Dialog
        open={detailId !== null}
        onOpenChange={(open) => {
          if (!open) setDetailId(null);
        }}
      >
        <AppDialogContent
          className="max-w-6xl"
          title={locale === "zh-CN" ? "请求详情" : "Request detail"}
        >
          {detailLoading || !detail ? (
            <div className="rounded-md border bg-background px-5 py-8 text-sm text-muted-foreground">
              {locale === "zh-CN" ? "正在加载详情..." : "Loading detail..."}
            </div>
          ) : (
            <div className="grid gap-5">
              <div className="grid gap-4 lg:grid-cols-5">
                <DetailStat
                  label={locale === "zh-CN" ? "模型组" : "Group"}
                  value={
                    detail.resolved_group_name ||
                    (locale === "zh-CN" ? "未命中" : "No match")
                  }
                />
                <DetailStat
                  label={locale === "zh-CN" ? "渠道" : "Channel"}
                  value={detail.channel_name || detail.channel_id || "n/a"}
                />
                <DetailStat
                  label={locale === "zh-CN" ? "状态" : "Status"}
                  value={String(detail.status_code)}
                />
                <DetailStat
                  label={locale === "zh-CN" ? "总 Token" : "Total token"}
                  value={formatCount(detail.total_tokens)}
                />
                <DetailStat
                  label={locale === "zh-CN" ? "总费用" : "Total cost"}
                  value={formatMoney(detail.total_cost_usd)}
                  accent
                />
              </div>

              {detail.error_message ? (
                <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-4 text-sm text-destructive">
                  <div className="flex items-start gap-3">
                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                    <span>{detail.error_message}</span>
                  </div>
                </div>
              ) : null}

              <Card className="py-0">
                <CardHeader className="mb-0 px-4 py-4 lg:px-5">
                  <CardTitle className="text-sm font-semibold text-foreground">
                    {locale === "zh-CN" ? "尝试链路" : "Attempts"}
                  </CardTitle>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {locale === "zh-CN"
                      ? "按实际命中与重试顺序记录"
                      : "Captured in routing and retry order"}
                  </p>
                </CardHeader>
                <CardContent className="px-4 pb-4 lg:px-5 lg:pb-5">
                  <AttemptChain detail={detail} locale={locale} />
                </CardContent>
              </Card>

              <div className="grid gap-5 xl:grid-cols-2">
                <Card className="overflow-hidden py-0">
                  <CardHeader className="border-b px-4 py-4">
                    <CardTitle className="text-sm font-semibold text-foreground">
                      {locale === "zh-CN" ? "请求内容" : "Request"}
                    </CardTitle>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatCount(detail.input_tokens)} tokens
                    </p>
                  </CardHeader>
                  <JsonPanel
                    content={detail.request_content}
                    emptyText={
                      locale === "zh-CN" ? "无输入内容" : "No request content"
                    }
                  />
                </Card>

                <Card className="overflow-hidden py-0">
                  <CardHeader className="border-b px-4 py-4">
                    <CardTitle className="text-sm font-semibold text-foreground">
                      {locale === "zh-CN" ? "响应内容" : "Response"}
                    </CardTitle>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatCount(detail.output_tokens)} tokens
                    </p>
                  </CardHeader>
                  <JsonPanel
                    content={detail.response_content}
                    emptyText={
                      locale === "zh-CN" ? "无输出内容" : "No response content"
                    }
                  />
                </Card>
              </div>
            </div>
          )}
        </AppDialogContent>
      </Dialog>
    </section>
  );
}
