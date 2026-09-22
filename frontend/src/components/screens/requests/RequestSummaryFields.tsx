import { Badge } from "@/components/ui/Badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { RequestLogItem } from "@/lib/api/requests";
import { titleForLocale } from "@/lib/I18nContext";
import { formatErrorSummary } from "./requestView";

/** Render the localized lifecycle outcome badge for a request. */
export function RequestOutcomeBadge({
  status,
  statusCode,
  locale,
  errorMessage,
}: {
  status: RequestLogItem["lifecycle_status"];
  statusCode: number | null | undefined;
  locale: "zh-CN" | "en-US";
  errorMessage?: string | null;
}) {
  const labelMap: Record<RequestLogItem["lifecycle_status"], [string, string]> =
    {
      connecting: ["连接中", "Connecting"],
      streaming: ["响应中", "Streaming"],
      succeeded: ["成功", "Success"],
      failed: ["失败", "Failed"],
      cancelled: ["已取消", "Cancelled"],
    };
  const label = titleForLocale(locale, ...labelMap[status]);
  const content = (
    <Badge
      variant="secondary"
      className="h-5 px-1.5 text-[11px] font-normal text-muted-foreground"
    >
      {label}
    </Badge>
  );
  if (status !== "failed") return content;

  const reason = [
    statusCode === null || statusCode === undefined
      ? null
      : `HTTP ${statusCode}`,
    formatErrorSummary(errorMessage),
  ]
    .filter(Boolean)
    .join("\n");
  if (!reason) return content;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex">{content}</span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm whitespace-pre-wrap" side="bottom">
        {reason}
      </TooltipContent>
    </Tooltip>
  );
}
