import { Badge } from "@/components/ui/Badge";
import type { RequestLogDetail } from "@/lib/api/requests";
import { cn } from "@/lib/classNames";
import { formatInternalCredentialLabel, formatMs } from "./requestDisplay";

/** A cooldown-skip is a routing-level skip: no upstream request was made. */
function isSkippedAttempt(attempt: RequestLogDetail["attempts"][number]) {
  return (
    !attempt.success && attempt.status_code === 503 && attempt.duration_ms === 0
  );
}

/** Render the ordered upstream attempts as a compact vertical list. */
export function AttemptChain({
  detail,
  locale,
}: {
  detail: RequestLogDetail;
  locale: "zh-CN" | "en-US";
}) {
  return (
    <div className="flex flex-col">
      {detail.attempts.map((attempt, index) => {
        const credentialLabel = attempt.channel_has_multiple_credentials
          ? formatInternalCredentialLabel(attempt, locale)
          : null;
        const errorDisplay = attempt.error_message?.trim() || null;
        return (
          <div
            key={`${attempt.channel_id}-${index}`}
            className="border-t py-2.5 first:border-t-0 first:pt-1 last:pb-1"
          >
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground">
                {index + 1}
              </span>
              <span className="truncate text-sm font-medium text-foreground">
                {attempt.channel_name}
              </span>
              {credentialLabel ? (
                <Badge
                  variant="secondary"
                  className="max-w-[140px] truncate px-2 py-0 text-[11px]"
                >
                  {credentialLabel}
                </Badge>
              ) : null}
              {attempt.model_name ? (
                <span className="max-w-[200px] truncate text-xs text-muted-foreground">
                  {attempt.model_name}
                </span>
              ) : null}
              <span className="ml-auto shrink-0 text-xs text-muted-foreground tabular-nums">
                {formatMs(attempt.duration_ms)}
              </span>
            </div>
            {errorDisplay ? (
              <div
                className={cn(
                  "mt-1.5 pl-[38px] text-xs break-words",
                  isSkippedAttempt(attempt)
                    ? "text-muted-foreground"
                    : "text-destructive",
                )}
              >
                {errorDisplay}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
