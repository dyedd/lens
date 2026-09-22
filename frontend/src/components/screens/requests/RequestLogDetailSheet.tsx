import type { ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/Sheet";
import type {
  RequestLogAttempt,
  RequestLogDetail,
  RequestLogItem,
} from "@/lib/api/requests";
import { cn } from "@/lib/classNames";
import { formatLogDateTime } from "@/lib/datetime";
import { titleForLocale } from "@/lib/I18nContext";
import { protocolLabel } from "@/lib/protocols";
import {
  formatChannelCredentialLabel,
  formatCount,
  formatGatewayKeyLabel,
  formatInternalCredentialLabel,
  formatMoney,
  formatMs,
  formatUserAgentDisplay,
  getResolvedGroupName,
  getSecondaryModelName,
  tryParseJsonValue,
} from "./requestView";

type Locale = "zh-CN" | "en-US";

function DetailRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] gap-3 border-b border-border/50 py-2.5 last:border-b-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <div
        className={cn(
          "min-w-0 break-words text-xs leading-5 text-foreground/86",
          mono && "font-mono",
        )}
      >
        {value ?? "-"}
      </div>
    </div>
  );
}

function DetailBlock({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-2">
      <h4 className="px-1 text-xs font-medium text-foreground/88">{title}</h4>
      <div className="rounded-lg border border-border/60 bg-background px-3">
        {children}
      </div>
    </section>
  );
}

/** Cooldown skip: routing rejected the target without an upstream call. */
function isCooldownSkip(attempt: RequestLogAttempt) {
  return (
    !attempt.success && attempt.status_code === 503 && attempt.duration_ms === 0
  );
}

function attemptResultLabel(attempt: RequestLogAttempt, locale: Locale) {
  if (attempt.success) return titleForLocale(locale, "成功", "Success");
  if (isCooldownSkip(attempt)) {
    return titleForLocale(locale, "跳过", "Skipped");
  }
  return titleForLocale(locale, "失败", "Failed");
}

function AttemptGroup({
  attempt,
  index,
  locale,
}: {
  attempt: RequestLogAttempt;
  index: number;
  locale: Locale;
}) {
  const skipped = isCooldownSkip(attempt);
  const modelName = attempt.model_name?.trim();
  const modelDisplay = modelName
    ? [modelName, attempt.reasoning_effort].filter(Boolean).join(" ")
    : null;
  return (
    <div className="border-b border-border/50 last:border-b-0">
      <DetailRow
        label={titleForLocale(
          locale,
          `尝试 ${index + 1}`,
          `Attempt ${index + 1}`,
        )}
        value={attemptResultLabel(attempt, locale)}
      />
      <DetailRow
        label={titleForLocale(locale, "渠道", "Channel")}
        value={attempt.channel_name || "-"}
      />
      {attempt.channel_has_multiple_credentials ? (
        <DetailRow
          label={titleForLocale(locale, "密钥", "Key")}
          value={formatInternalCredentialLabel(attempt, locale)}
        />
      ) : null}
      {modelDisplay ? (
        <DetailRow
          label={titleForLocale(locale, "模型", "Model")}
          value={modelDisplay}
          mono
        />
      ) : null}
      {!skipped &&
      attempt.status_code !== null &&
      attempt.status_code !== undefined ? (
        <DetailRow label="HTTP" value={attempt.status_code} mono />
      ) : null}
      {attempt.duration_ms > 0 ? (
        <DetailRow
          label={titleForLocale(locale, "耗时", "Latency")}
          value={formatMs(attempt.duration_ms)}
          mono
        />
      ) : null}
      {attempt.error_message?.trim() ? (
        <DetailRow
          label={titleForLocale(locale, "错误", "Error")}
          value={attempt.error_message.trim()}
        />
      ) : null}
    </div>
  );
}

function formatJsonText(raw: string) {
  const value = raw.trim();
  if (!value) return "";
  const parsed = tryParseJsonValue(value);
  if (parsed === null) return value;
  try {
    return JSON.stringify(parsed, null, 2);
  } catch {
    return value;
  }
}

function JsonSection({
  title,
  value,
  locale,
  loading = false,
}: {
  title: string;
  value: string;
  locale: Locale;
  loading?: boolean;
}) {
  const formatted = formatJsonText(value);
  const empty = !formatted;
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-3 px-1">
        <h4 className="text-xs font-medium text-foreground/88">{title}</h4>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs shadow-none"
          disabled={loading || empty}
          onClick={() => void copyText(formatted, locale)}
        >
          JSON
        </Button>
      </div>
      {loading ? (
        <p className="rounded-md bg-muted/35 px-3 py-6 text-center text-xs leading-5 text-muted-foreground">
          {titleForLocale(locale, "正在加载...", "Loading...")}
        </p>
      ) : empty ? (
        <p className="rounded-md bg-muted/35 px-3 py-2 text-xs leading-5 text-muted-foreground">
          {titleForLocale(locale, "无内容", "No content")}
        </p>
      ) : (
        <pre className="max-h-[320px] overflow-auto rounded-lg border border-border/60 bg-muted/35 p-3 text-xs leading-5 text-foreground/86">
          <code>{formatted}</code>
        </pre>
      )}
    </section>
  );
}

async function copyText(value: string, locale: Locale) {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(titleForLocale(locale, "已复制", "Copied"));
  } catch {
    toast.error(titleForLocale(locale, "复制失败", "Failed to copy"));
  }
}

function statusLabel(
  status: RequestLogItem["lifecycle_status"],
  locale: Locale,
) {
  const labels: Record<RequestLogItem["lifecycle_status"], [string, string]> = {
    connecting: ["连接中", "Connecting"],
    streaming: ["响应中", "Streaming"],
    succeeded: ["成功", "Success"],
    failed: ["失败", "Failed"],
    cancelled: ["已取消", "Cancelled"],
  };
  return titleForLocale(locale, ...labels[status]);
}

/** Request log detail sheet. */
export function RequestLogDetailSheet({
  item,
  detail,
  loading,
  error,
  locale,
  timeZone,
  relayLogBodyEnabled,
  onClose,
}: {
  item: RequestLogItem | null;
  detail: RequestLogDetail | undefined;
  loading: boolean;
  error: unknown;
  locale: Locale;
  timeZone: string;
  relayLogBodyEnabled: boolean;
  onClose: () => void;
}) {
  const record = detail ?? item;
  const modelName = record ? getResolvedGroupName(record) : "";
  const upstream = record ? getSecondaryModelName(record) : null;
  const time = record
    ? formatLogDateTime(record.created_at, locale, timeZone)
    : "";

  return (
    <Sheet
      open={Boolean(item) || loading}
      onOpenChange={(open) => !open && onClose()}
    >
      <SheetContent className="sm:max-w-[480px]">
        <SheetHeader>
          <SheetTitle>
            {titleForLocale(locale, "请求日志详情", "Request log detail")}
          </SheetTitle>
          <SheetDescription>
            {record
              ? `${modelName} · ${time}`
              : titleForLocale(locale, "加载中...", "Loading...")}
          </SheetDescription>
        </SheetHeader>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 pb-6">
          {error ? (
            <p className="text-xs text-muted-foreground">
              {error instanceof Error
                ? error.message
                : titleForLocale(
                    locale,
                    "无法读取日志详情",
                    "Unable to read log detail",
                  )}
            </p>
          ) : null}
          {!record && loading ? (
            <p className="text-xs text-muted-foreground">
              {titleForLocale(locale, "正在加载详情...", "Loading detail...")}
            </p>
          ) : null}
          {record ? (
            <>
              <DetailBlock title={titleForLocale(locale, "请求", "Request")}>
                <DetailRow label="ID" value={record.id} mono />
                <DetailRow
                  label={titleForLocale(locale, "时间", "Time")}
                  value={time}
                />
                <DetailRow
                  label={titleForLocale(locale, "状态", "Status")}
                  value={statusLabel(record.lifecycle_status, locale)}
                />
                {record.lifecycle_status === "failed" &&
                record.status_code !== null &&
                record.status_code !== undefined ? (
                  <DetailRow label="HTTP" value={record.status_code} mono />
                ) : null}
                <DetailRow
                  label={titleForLocale(locale, "客户端", "Client")}
                  value={
                    record.user_agent
                      ? formatUserAgentDisplay(record.user_agent, locale)
                      : "-"
                  }
                />
                <DetailRow
                  label={titleForLocale(locale, "模式", "Mode")}
                  value={
                    record.is_stream
                      ? titleForLocale(locale, "流式", "Stream")
                      : titleForLocale(locale, "非流式", "Non-stream")
                  }
                />
                {record.error_message?.trim() ? (
                  <DetailRow
                    label={titleForLocale(locale, "错误", "Error")}
                    value={record.error_message.trim()}
                  />
                ) : null}
              </DetailBlock>

              <DetailBlock
                title={titleForLocale(locale, "模型路由", "Routing")}
              >
                <DetailRow
                  label={titleForLocale(locale, "模型组", "Group")}
                  value={
                    record.reasoning_effort
                      ? `${modelName} ${record.reasoning_effort}`
                      : modelName
                  }
                  mono
                />
                <DetailRow
                  label={titleForLocale(locale, "上游模型", "Upstream model")}
                  value={upstream || record.upstream_model_name || "-"}
                  mono
                />
                <DetailRow
                  label={titleForLocale(locale, "渠道", "Channel")}
                  value={formatChannelCredentialLabel(record, locale)}
                />
                {record.channel_has_multiple_credentials ? (
                  <DetailRow
                    label={titleForLocale(locale, "密钥", "Key")}
                    value={formatInternalCredentialLabel(record, locale)}
                  />
                ) : null}
                {record.gateway_key_id ? (
                  <DetailRow
                    label="API Key"
                    value={formatGatewayKeyLabel(record, locale)}
                  />
                ) : null}
                <DetailRow
                  label={titleForLocale(locale, "协议", "Protocol")}
                  value={protocolLabel(record.protocol, locale)}
                />
                {record.rate_multiplier === null ? null : (
                  <DetailRow
                    label={titleForLocale(locale, "倍率", "Rate")}
                    value={`${record.rate_multiplier}x`}
                    mono
                  />
                )}
              </DetailBlock>

              <DetailBlock title={titleForLocale(locale, "用量计费", "Usage")}>
                <DetailRow
                  label={titleForLocale(locale, "费用", "Cost")}
                  value={formatMoney(record.total_cost_usd)}
                  mono
                />
                {record.billing_mode === "non_tokens" ? (
                  <DetailRow
                    label={titleForLocale(locale, "图片数", "Images")}
                    value={formatCount(record.billing_units)}
                    mono
                  />
                ) : (
                  <>
                    <DetailRow
                      label={titleForLocale(locale, "总 Token", "Total tokens")}
                      value={formatCount(record.total_tokens)}
                      mono
                    />
                    <DetailRow
                      label={titleForLocale(locale, "输入", "Input")}
                      value={formatCount(record.input_tokens)}
                      mono
                    />
                    <DetailRow
                      label={titleForLocale(locale, "图片输入", "Image input")}
                      value={formatCount(record.image_input_tokens)}
                      mono
                    />
                    <DetailRow
                      label={titleForLocale(locale, "输出", "Output")}
                      value={formatCount(record.output_tokens)}
                      mono
                    />
                    <DetailRow
                      label={titleForLocale(locale, "缓存读取", "Cache read")}
                      value={formatCount(record.cache_read_input_tokens)}
                      mono
                    />
                    <DetailRow
                      label={titleForLocale(locale, "缓存写入", "Cache write")}
                      value={formatCount(record.cache_write_input_tokens)}
                      mono
                    />
                    <DetailRow
                      label={titleForLocale(locale, "首字", "First token")}
                      value={formatMs(record.first_token_latency_ms)}
                      mono
                    />
                  </>
                )}
                <DetailRow
                  label={titleForLocale(locale, "耗时", "Latency")}
                  value={formatMs(record.latency_ms)}
                  mono
                />
              </DetailBlock>

              {record.lifecycle_status === "failed" &&
              detail &&
              detail.attempts.length > 0 ? (
                <DetailBlock title={titleForLocale(locale, "尝试", "Attempts")}>
                  {detail.attempts.map((attempt, index) => (
                    <AttemptGroup
                      key={`${attempt.channel_id}-${index}`}
                      attempt={attempt}
                      index={index}
                      locale={locale}
                    />
                  ))}
                </DetailBlock>
              ) : null}

              {relayLogBodyEnabled && (detail || (loading && !error)) ? (
                <>
                  <JsonSection
                    title={titleForLocale(locale, "请求正文", "Request")}
                    value={detail?.request_content ?? ""}
                    locale={locale}
                    loading={loading && !detail}
                  />
                  <JsonSection
                    title={titleForLocale(locale, "响应正文", "Response")}
                    value={detail?.response_content ?? ""}
                    locale={locale}
                    loading={loading && !detail}
                  />
                </>
              ) : null}
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
