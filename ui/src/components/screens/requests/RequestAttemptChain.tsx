"use client";

import { Badge } from "@/components/ui/Badge";
import type { RequestLogDetail } from "@/lib/api";
import { cn } from "@/lib/utils";
import { RequestOutcomeBadge } from "./RequestSummaryFields";
import {
  formatErrorDisplay,
  formatInternalCredentialLabel,
  formatMs,
} from "./requestLogUtils";

/** Render the ordered upstream attempts for a request. */
export function AttemptChain({
  detail,
  locale,
}: {
  detail: RequestLogDetail;
  locale: "zh-CN" | "en-US";
}) {
  const attempts = detail.attempts;

  return (
    <div className="overflow-hidden rounded-xl bg-muted/20">
      {attempts.map((attempt, index) => {
        const errorDisplay = formatErrorDisplay(attempt.error_message);
        const isConnectingAttempt =
          detail.lifecycle_status === "connecting" &&
          index === attempts.length - 1;
        const credentialLabel = attempt.channel_has_multiple_credentials
          ? formatInternalCredentialLabel(attempt, locale)
          : null;
        return (
          <div
            key={`${attempt.channel_id}-${index}`}
            className={cn(
              "border-t px-4 first:border-t-0",
              errorDisplay ? "py-3" : "py-2.5",
            )}
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full bg-background px-2 text-xs font-semibold text-muted-foreground">
                  {index + 1}
                </span>
                <span className="max-w-[220px] truncate text-sm font-medium text-foreground">
                  {attempt.channel_name}
                </span>
                {credentialLabel ? (
                  <Badge variant="secondary" className="max-w-[160px] truncate">
                    {credentialLabel}
                  </Badge>
                ) : null}
                {attempt.model_name ? (
                  <span className="max-w-[220px] truncate text-xs text-muted-foreground">
                    {attempt.model_name}
                  </span>
                ) : null}
                <RequestOutcomeBadge
                  status={
                    isConnectingAttempt
                      ? "connecting"
                      : attempt.success
                        ? "succeeded"
                        : "failed"
                  }
                  statusCode={attempt.status_code}
                  locale={locale}
                  errorMessage={errorDisplay}
                />
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{formatMs(attempt.duration_ms)}</span>
              </div>
            </div>
            {errorDisplay ? (
              <div className="mt-2 rounded-md bg-destructive/10 px-3 py-2 text-xs whitespace-pre-wrap break-words text-destructive">
                {errorDisplay}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
