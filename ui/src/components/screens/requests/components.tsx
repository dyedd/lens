"use client";

import type * as React from "react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { RequestLogItem } from "@/lib/api";
import { cn } from "@/lib/utils";
import { titleForLocale } from "./shared";

export { SeriesChip } from "@/lib/model-prefix";

export function RequestOutcomeBadge({
  status,
  success,
  statusCode,
  locale,
  errorMessage,
}: {
  status: RequestLogItem["lifecycle_status"];
  success: boolean;
  statusCode: number | null | undefined;
  locale: "zh-CN" | "en-US";
  errorMessage?: string | null;
}) {
  const running = status === "connecting" || status === "streaming";
  const labelMap: Record<RequestLogItem["lifecycle_status"], [string, string]> =
    {
      connecting: ["连接中", "Connecting"],
      streaming: ["响应中", "Streaming"],
      succeeded: ["成功", "Success"],
      failed: ["失败", "Failed"],
    };
  const label = titleForLocale(locale, ...labelMap[status]);
  const text =
    statusCode === null || statusCode === undefined
      ? label
      : `${statusCode} · ${label}`;

  const content = (
    <Badge
      variant="outline"
      className={cn(
        "rounded-full border-0 px-3 py-1 text-xs font-medium",
        running
          ? "bg-muted text-muted-foreground"
          : success
            ? "bg-primary/10 text-primary"
            : "bg-destructive/12 text-destructive",
      )}
    >
      {text}
    </Badge>
  );

  if (success || running || !errorMessage?.trim()) {
    return content;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex">{content}</span>
      </TooltipTrigger>
      <TooltipContent
        className="max-w-sm whitespace-pre-wrap break-words"
        side="bottom"
      >
        {errorMessage}
      </TooltipContent>
    </Tooltip>
  );
}

export function ProtocolBadge({
  protocol,
}: {
  protocol: RequestLogItem["protocol"];
}) {
  const labelMap = {
    openai_chat: "chat",
    openai_responses: "responses",
    openai_embedding: "embedding",
    rerank: "rerank",
    anthropic: "anthropic",
    gemini: "gemini",
    openai_image: "image",
  } as const;

  return (
    <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-medium">
      {labelMap[protocol] ?? protocol}
    </Badge>
  );
}

export function RequestMetric({
  icon,
  label,
  value,
  valueClassName,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <div className="flex min-h-[58px] min-w-0 items-start gap-2.5 rounded-xl border bg-background px-3 py-2.5">
      <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-muted/35 text-muted-foreground">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[11px] leading-4 text-muted-foreground">
          {label}
        </div>
        <div
          className={cn(
            "mt-1 whitespace-normal break-words text-[13px] font-semibold leading-4 text-foreground tabular-nums",
            valueClassName,
          )}
        >
          {value}
        </div>
      </div>
    </div>
  );
}

export function RequestMeta({
  icon,
  value,
  className,
  tooltip,
}: {
  icon: React.ReactNode;
  value: string;
  className?: string;
  tooltip?: string;
}) {
  const meta = (
    <div
      className={cn(
        "flex h-8 min-w-0 max-w-full items-center gap-2 rounded-full bg-muted/[0.22] px-3 text-xs font-medium text-muted-foreground",
        className,
      )}
    >
      <span className="shrink-0 text-muted-foreground/90">{icon}</span>
      <span className="truncate leading-none">{value}</span>
    </div>
  );

  if (!tooltip) return meta;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{meta}</TooltipTrigger>
      <TooltipContent
        className="max-w-sm whitespace-pre-wrap break-words"
        side="bottom"
        align="start"
      >
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
}
