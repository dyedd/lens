import { AlertCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/Alert";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import type { RequestLogDetail } from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { AttemptChain } from "./RequestCard";
import { formatErrorDisplay } from "./requestLogUtils";
import { RequestPayloadViewer } from "./RequestPayloadViewer";

type DetailState = {
  data: RequestLogDetail | undefined;
  error: unknown;
  isError: boolean;
  isLoading: boolean;
};

type RequestLogDialogsProps = {
  attemptDetailId: number | null;
  attemptState: DetailState;
  detailId: number | null;
  detailState: DetailState;
  locale: Locale;
  relayLogBodyEnabled: boolean;
  onAttemptClose: () => void;
  onDetailClose: () => void;
};

function DetailError({
  error,
  locale,
  attempt,
}: {
  error: unknown;
  locale: Locale;
  attempt?: boolean;
}) {
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertTitle>
        {attempt
          ? titleForLocale(
              locale,
              "尝试链路加载失败",
              "Failed to load attempts",
            )
          : titleForLocale(locale, "详情加载失败", "Failed to load detail")}
      </AlertTitle>
      <AlertDescription>
        {error instanceof Error
          ? error.message
          : attempt
            ? titleForLocale(
                locale,
                "无法读取尝试链路",
                "Unable to read attempts",
              )
            : titleForLocale(
                locale,
                "无法读取日志详情",
                "Unable to read log detail",
              )}
      </AlertDescription>
    </Alert>
  );
}

/** Render request payload and attempt-chain dialogs. */
export function RequestLogDialogs(props: RequestLogDialogsProps) {
  const {
    attemptDetailId,
    attemptState,
    detailId,
    detailState,
    locale,
    relayLogBodyEnabled,
    onAttemptClose,
    onDetailClose,
  } = props;
  return (
    <>
      <Dialog
        open={relayLogBodyEnabled && detailId !== null}
        onOpenChange={(open) => {
          if (!open) onDetailClose();
        }}
      >
        <AppDialogContent
          className="max-w-6xl"
          title={titleForLocale(locale, "日志详情", "Log detail")}
        >
          {detailState.isError ? (
            <DetailError error={detailState.error} locale={locale} />
          ) : detailState.isLoading || !detailState.data ? (
            <div className="rounded-md border bg-background px-5 py-8 text-sm text-muted-foreground">
              {titleForLocale(locale, "正在加载详情...", "Loading detail...")}
            </div>
          ) : (
            <div className="grid min-h-[60dvh] overflow-hidden sm:min-h-[560px] xl:grid-cols-2">
              <RequestPayloadViewer
                key={`request-${detailState.data.id}`}
                title={titleForLocale(locale, "请求内容", "Request")}
                content={detailState.data.request_content}
                emptyText={titleForLocale(
                  locale,
                  "无输入内容",
                  "No request content",
                )}
                locale={locale}
              />
              <RequestPayloadViewer
                key={`response-${detailState.data.id}`}
                className="border-t xl:border-t-0 xl:border-l"
                title={titleForLocale(locale, "响应内容", "Response")}
                content={detailState.data.response_content}
                emptyText={titleForLocale(
                  locale,
                  "无输出内容",
                  "No response content",
                )}
                locale={locale}
              />
            </div>
          )}
        </AppDialogContent>
      </Dialog>
      <Dialog
        open={attemptDetailId !== null}
        onOpenChange={(open) => {
          if (!open) onAttemptClose();
        }}
      >
        <AppDialogContent
          className="max-w-4xl"
          title={titleForLocale(locale, "尝试链路", "Attempts")}
        >
          {attemptState.isError ? (
            <DetailError error={attemptState.error} locale={locale} attempt />
          ) : attemptState.isLoading || !attemptState.data ? (
            <div className="rounded-md border bg-background px-5 py-8 text-sm text-muted-foreground">
              {titleForLocale(
                locale,
                "正在加载尝试链路...",
                "Loading attempts...",
              )}
            </div>
          ) : (
            <div className="grid gap-4">
              {formatErrorDisplay(attemptState.data.error_message) ? (
                <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-4 text-sm text-destructive">
                  <div className="flex items-start gap-3">
                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                    <span className="whitespace-pre-wrap break-words">
                      {formatErrorDisplay(attemptState.data.error_message)}
                    </span>
                  </div>
                </div>
              ) : null}
              <AttemptChain detail={attemptState.data} locale={locale} />
            </div>
          )}
        </AppDialogContent>
      </Dialog>
    </>
  );
}
