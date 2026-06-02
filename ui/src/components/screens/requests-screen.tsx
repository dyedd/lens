"use client";

import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import JsonView from "@uiw/react-json-view";
import { toast } from "sonner";
import {
  AlertCircle,
  ArrowDownToLine,
  ArrowUp,
  ArrowUpFromLine,
  CheckCheck,
  Clock3,
  Copy,
  Database,
  DollarSign,
  Filter,
  Fingerprint,
  KeyRound,
  LayoutGrid,
  RefreshCcw,
  RotateCcw,
  ServerCog,
  Trash2,
  Upload,
  Waypoints,
  Zap,
} from "lucide-react";
import {
  ApiError,
  GatewayApiKey,
  ProtocolKind,
  RequestLogDetail,
  RequestLogItem,
  RequestLogPage,
  apiRequest,
} from "@/lib/api";
import { formatLogDateTime } from "@/lib/datetime";
import { useAppTimeZone } from "@/hooks/use-app-time-zone";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import {
  getModelFamilyKey,
  getModelFamilyLabel,
  ModelAvatar,
} from "@/lib/model-icons";
import { Dialog, AppDialogContent } from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ToolbarSearchInput } from "@/components/ui/toolbar-search-input";

const PAGE_SIZE = 20;
const REQUEST_LOG_DETAIL_GC_TIME = 60_000;

type ModelPrefixOption = {
  key: string;
  label: string;
  sampleModel: string;
};
type SelectedModelPrefix = "all" | string;
type StatusFilter = "all" | "running" | "success" | "failed";
type SortMode = "latest" | "cost" | "latency" | "tokens";
type JsonLike =
  | null
  | boolean
  | number
  | string
  | JsonLike[]
  | { [key: string]: JsonLike };

const HIDDEN_USER_AGENT_PRODUCTS = new Set(["vscode"]);

function titleForLocale(locale: "zh-CN" | "en-US", zh: string, en: string) {
  return locale === "zh-CN" ? zh : en;
}

function formatMs(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

function formatMoney(value: number | null | undefined) {
  return `$${(value ?? 0).toFixed(6)}`;
}

function formatMaybeMoney(value: number | null | undefined, pending: boolean) {
  if (pending && !value) return "-";
  return formatMoney(value);
}

function formatCount(value: number) {
  return value.toLocaleString();
}

function formatMaybeCount(value: number, pending: boolean) {
  if (pending && !value) return "-";
  return formatCount(value);
}

function formatUserAgentDisplay(value: string, locale: "zh-CN" | "en-US") {
  const raw = value.trim();
  const parts: string[] = [];
  const products = raw.matchAll(/\b([A-Za-z][A-Za-z0-9._-]*)\/([^\s;)]+)/g);
  const client = Array.from(products).find(
    (match) => !HIDDEN_USER_AGENT_PRODUCTS.has(match[1].toLowerCase()),
  );

  if (client) {
    parts.push(`${client[1]}/${client[2]}`);
  } else {
    parts.push(titleForLocale(locale, "未知客户端", "Unknown client"));
  }

  if (/\bWindows\b/i.test(raw)) {
    parts.push("Windows");
  } else if (/\bMac OS X\b|\bmacOS\b|\bMacintosh\b/i.test(raw)) {
    parts.push("macOS");
  } else if (/\bLinux\b/i.test(raw)) {
    parts.push("Linux");
  }

  return parts.join(" · ");
}

function shortenGatewayKeyId(value?: string | null) {
  if (!value) return "";
  if (value.length <= 10) return value;
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function formatGatewayKeyLabel(
  item: Pick<RequestLogItem, "gateway_key_id" | "gateway_key_remark">,
  locale: "zh-CN" | "en-US",
) {
  return (
    item.gateway_key_remark?.trim() ||
    shortenGatewayKeyId(item.gateway_key_id) ||
    titleForLocale(locale, "未绑定 API Key", "No API key")
  );
}

function formatGatewayKeyOptionLabel(
  item: Pick<GatewayApiKey, "id" | "remark">,
) {
  return item.remark.trim() || shortenGatewayKeyId(item.id);
}

function tryParseJsonValue(value: string) {
  try {
    return JSON.parse(value) as JsonLike;
  } catch {
    return null;
  }
}

function formatHtmlErrorContent(value: string) {
  return value
    .replace(/>\s*</g, ">\n<")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(
      /<\/(p|div|section|article|header|footer|main|h1|h2|h3|h4|h5|h6|li|ul|ol|pre|code)>/gi,
      "$&\n",
    )
    .trim();
}

function formatJsonErrorContent(prefix: string, value: JsonLike) {
  const jsonText = JSON.stringify(value, null, 2);
  if (!jsonText) return prefix.trim() || null;
  return jsonText;
}

function formatErrorDisplay(value: string | null | undefined) {
  const raw = value?.trim();
  if (!raw) return null;

  const directParsed = tryParseJsonValue(raw);
  if (directParsed !== null) {
    return formatJsonErrorContent("", directParsed);
  }

  const jsonStart = raw.indexOf("{");
  if (jsonStart > 0) {
    const nestedParsed = tryParseJsonValue(raw.slice(jsonStart));
    if (nestedParsed !== null) {
      return formatJsonErrorContent(raw.slice(0, jsonStart), nestedParsed);
    }
  }

  if (/<!doctype html|<html|<head|<body|<title/i.test(raw)) {
    return formatHtmlErrorContent(raw);
  }

  return raw;
}

function getResolvedGroupName(
  item: Pick<
    RequestLogItem,
    "requested_group_name" | "resolved_group_name" | "upstream_model_name"
  >,
) {
  return (
    item.resolved_group_name ||
    item.requested_group_name ||
    item.upstream_model_name ||
    "n/a"
  );
}

function getModelChain(
  item: Pick<
    RequestLogItem,
    "requested_group_name" | "resolved_group_name" | "upstream_model_name"
  >,
) {
  const requested = item.requested_group_name?.trim();
  const resolved = item.resolved_group_name?.trim();
  if (requested && resolved && requested !== resolved) {
    return `${requested} -> ${resolved}`;
  }
  return resolved || requested || item.upstream_model_name || "n/a";
}

function getSecondaryModelName(
  item: Pick<
    RequestLogItem,
    "requested_group_name" | "resolved_group_name" | "upstream_model_name"
  >,
) {
  const resolved = item.resolved_group_name?.trim();
  const upstream = item.upstream_model_name?.trim();
  if (upstream && upstream !== resolved) {
    return upstream;
  }
  return null;
}

function buildPaginationItems(currentPage: number, totalPages: number) {
  if (totalPages <= 1) return [1];
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  if (currentPage <= 2) {
    return [1, 2, 3, "ellipsis", totalPages] as const;
  }

  if (currentPage >= totalPages - 2) {
    return [1, "ellipsis", totalPages - 2, totalPages - 1, totalPages] as const;
  }

  return [
    1,
    "ellipsis",
    currentPage,
    currentPage + 1,
    "ellipsis",
    totalPages,
  ] as const;
}

function RequestOutcomeBadge({
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

function ProtocolBadge({ protocol }: { protocol: RequestLogItem["protocol"] }) {
  const labelMap = {
    openai_chat: "chat",
    openai_responses: "responses",
    openai_embedding: "embedding",
    rerank: "rerank",
    anthropic: "anthropic",
    gemini: "gemini",
  } as const;

  return (
    <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-medium">
      {labelMap[protocol] ?? protocol}
    </Badge>
  );
}

function normalizeLineBreaks(value: string) {
  return value.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

type JsonContainer = JsonLike[] | { [key: string]: JsonLike };
type ParsedViewerContent =
  | { isJson: true; data: JsonContainer }
  | { isJson: false; data: string };

const JSON_VIEW_STYLE = {
  fontSize: "12px",
  fontFamily:
    'var(--font-mono), ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
  backgroundColor: "transparent",
  "--w-rjv-background-color": "transparent",
  "--w-rjv-font-family":
    'var(--font-mono), ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
  "--w-rjv-color": "var(--foreground)",
  "--w-rjv-key-number": "var(--primary)",
  "--w-rjv-key-string": "var(--primary)",
  "--w-rjv-line-color": "var(--border)",
  "--w-rjv-arrow-color": "var(--muted-foreground)",
  "--w-rjv-info-color": "var(--muted-foreground)",
  "--w-rjv-curlybraces-color": "var(--foreground)",
  "--w-rjv-colon-color": "var(--muted-foreground)",
  "--w-rjv-brackets-color": "var(--foreground)",
  "--w-rjv-ellipsis-color": "var(--muted-foreground)",
  "--w-rjv-quotes-color": "var(--muted-foreground)",
  "--w-rjv-quotes-string-color": "var(--chart-2)",
  "--w-rjv-type-string-color": "var(--chart-2)",
  "--w-rjv-type-int-color": "var(--chart-4)",
  "--w-rjv-type-float-color": "var(--chart-4)",
  "--w-rjv-type-bigint-color": "var(--chart-4)",
  "--w-rjv-type-boolean-color": "var(--chart-3)",
  "--w-rjv-type-null-color": "var(--muted-foreground)",
  "--w-rjv-type-undefined-color": "var(--muted-foreground)",
} as CSSProperties;

function parseViewerContent(content: string): ParsedViewerContent {
  try {
    const parsed = JSON.parse(content) as JsonLike;
    if (parsed && typeof parsed === "object") {
      return { isJson: true, data: parsed };
    }
  } catch {
    return { isJson: false, data: content };
  }
  return { isJson: false, data: content };
}

function getJsonLineHeights(root: HTMLElement | null) {
  if (!root) return [];

  const lineNodes = root.querySelectorAll<HTMLElement>(
    ".w-rjv-inner > span, .w-rjv-line, .w-rjv-inner > div:not(.w-rjv-wrap)",
  );

  return Array.from(lineNodes, (node) =>
    Math.max(Math.round(node.getBoundingClientRect().height), 24),
  );
}

function lineHeightsEqual(a: number[], b: number[]) {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function LineNumbersColumn({ lineHeights }: { lineHeights: number[] }) {
  return (
    <div className="sticky left-0 z-10 border-r bg-background/95 py-3 backdrop-blur-xs">
      {lineHeights.map((height, index) => (
        <div
          key={index}
          className="flex select-none items-start justify-end pr-3 font-mono text-[11px] leading-6 text-muted-foreground/70"
          style={{ height }}
        >
          {index + 1}
        </div>
      ))}
    </div>
  );
}

function LineNumberedCode({ text }: { text: string }) {
  const lines = useMemo(() => normalizeLineBreaks(text).split("\n"), [text]);

  return (
    <div className="max-h-[60dvh] overflow-auto sm:max-h-[560px]">
      <div className="min-w-full py-3">
        {lines.map((line, index) => (
          <div
            key={index}
            className="grid grid-cols-[44px_minmax(0,1fr)] font-mono text-xs leading-6"
          >
            <div className="select-none border-r bg-muted/20 pr-3 text-right text-[11px] text-muted-foreground/70">
              {index + 1}
            </div>
            <pre className="m-0 min-w-0 whitespace-pre-wrap break-words px-4 text-foreground">
              {line || " "}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

function JsonViewer({
  title,
  content,
  emptyText,
  locale,
  className,
}: {
  title: string;
  content?: string | null;
  emptyText: string;
  locale: "zh-CN" | "en-US";
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [ready, setReady] = useState(false);
  const [lineHeights, setLineHeights] = useState<number[]>([]);
  const jsonViewRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!content) return;

    const timer = window.setTimeout(() => setReady(true), 80);
    return () => window.clearTimeout(timer);
  }, [content]);

  async function copyContent() {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      toast.success(titleForLocale(locale, "已复制内容", "Copied content"));
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error(titleForLocale(locale, "复制失败", "Failed to copy"));
    }
  }

  const parsed = useMemo(() => {
    if (!ready || !content) return null;
    return parseViewerContent(content);
  }, [content, ready]);

  useEffect(() => {
    if (!parsed?.isJson || !jsonViewRef.current) return;

    const root = jsonViewRef.current;
    let frameId = 0;

    const measure = () => {
      frameId = 0;
      const next = getJsonLineHeights(root);
      setLineHeights((current) =>
        lineHeightsEqual(current, next) ? current : next,
      );
    };

    const scheduleMeasure = () => {
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
      frameId = window.requestAnimationFrame(measure);
    };

    scheduleMeasure();

    const mutationObserver = new MutationObserver(scheduleMeasure);
    mutationObserver.observe(root, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    const resizeObserver = new ResizeObserver(scheduleMeasure);
    resizeObserver.observe(root);

    return () => {
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
      mutationObserver.disconnect();
      resizeObserver.disconnect();
    };
  }, [parsed]);

  return (
    <section
      className={cn(
        "flex min-h-[60dvh] min-w-0 flex-col bg-background sm:min-h-[560px]",
        className,
      )}
    >
      <header className="flex shrink-0 flex-col items-start justify-between gap-3 px-3 py-3 sm:flex-row sm:items-center sm:px-4">
        <div className="text-sm font-semibold text-foreground">{title}</div>
        <div className="flex flex-wrap items-center gap-2">
          {parsed?.isJson ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setExpanded((current) => !current)}
            >
              {expanded
                ? titleForLocale(locale, "折叠", "Collapse")
                : titleForLocale(locale, "展开", "Expand")}
            </Button>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => void copyContent()}
            disabled={!content}
          >
            {copied ? (
              <CheckCheck data-icon="inline-start" />
            ) : (
              <Copy data-icon="inline-start" />
            )}
            {titleForLocale(locale, "复制", "Copy")}
          </Button>
        </div>
      </header>

      <div className="min-h-0 flex-1">
        {!content ? (
          <div className="px-4 py-6 text-xs text-muted-foreground">
            {emptyText}
          </div>
        ) : !ready ? (
          <div className="px-4 py-6 text-xs text-muted-foreground">
            {titleForLocale(locale, "正在准备内容...", "Preparing content...")}
          </div>
        ) : parsed?.isJson ? (
          <div className="max-h-[60dvh] overflow-auto sm:max-h-[560px]">
            <div className="grid min-w-full grid-cols-[44px_minmax(0,1fr)]">
              <LineNumbersColumn lineHeights={lineHeights} />
              <div className="min-w-0 px-3 py-3 sm:px-4">
                <div ref={jsonViewRef} className="json-view-shell">
                  <JsonView
                    value={parsed.data as object}
                    collapsed={expanded ? false : 2}
                    displayDataTypes={false}
                    displayObjectSize={false}
                    enableClipboard={false}
                    highlightUpdates={false}
                    shortenTextAfterLength={220}
                    style={JSON_VIEW_STYLE}
                  />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <LineNumberedCode text={parsed?.data ?? content} />
        )}
      </div>
    </section>
  );
}

function RequestMetric({
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

function RequestMeta({
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

function SeriesChip({
  selected,
  label,
  sampleModel,
  onClick,
  isAll = false,
}: {
  selected: boolean;
  label: string;
  sampleModel: string;
  onClick: () => void;
  isAll?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        "group flex min-w-[76px] snap-start items-center justify-center rounded-[22px] border bg-card px-4 py-4 text-center transition-all",
        selected
          ? "border-primary bg-primary/[0.05] shadow-[0_0_0_1px_rgba(37,99,235,0.08)]"
          : "border-border/70 hover:border-primary/25 hover:bg-muted/20",
      )}
    >
      <span
        className={cn(
          "flex size-11 items-center justify-center rounded-2xl border bg-background",
          selected ? "border-primary/20 bg-primary/[0.06]" : "border-border/60",
        )}
      >
        {isAll ? (
          <LayoutGrid
            size={20}
            className={selected ? "text-primary" : "text-muted-foreground"}
          />
        ) : (
          <ModelAvatar name={sampleModel} size={28} />
        )}
      </span>
    </button>
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
          credential_id: null,
          credential_name: "",
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
      {attempts.map((attempt, index) => {
        const errorDisplay = formatErrorDisplay(attempt.error_message);
        return (
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
                  {attempt.credential_name || attempt.credential_id ? (
                    <Badge
                      variant="secondary"
                      className="max-w-[160px] truncate"
                    >
                      {attempt.credential_name || attempt.credential_id}
                    </Badge>
                  ) : null}
                  {attempt.model_name ? (
                    <span className="max-w-[220px] truncate text-xs text-muted-foreground">
                      {attempt.model_name}
                    </span>
                  ) : null}
                  <RequestOutcomeBadge
                    status={attempt.success ? "succeeded" : "failed"}
                    success={attempt.success}
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
                <div className="mt-3 rounded-md bg-destructive/10 px-3 py-2 text-xs whitespace-pre-wrap break-words text-destructive">
                  {errorDisplay}
                </div>
              ) : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function RequestCard({
  item,
  locale,
  timeZone,
  now,
  onOpenDetail,
  onOpenAttempts,
}: {
  item: RequestLogItem;
  locale: "zh-CN" | "en-US";
  timeZone?: string;
  now: number;
  onOpenDetail: () => void;
  onOpenAttempts: () => void;
}) {
  const primaryModelName = getResolvedGroupName(item);
  const modelChain = getModelChain(item);
  const secondaryModelName = getSecondaryModelName(item);
  const attemptCount = Number.isFinite(item.attempt_count)
    ? item.attempt_count
    : 0;
  const errorDisplay = formatErrorDisplay(item.error_message);
  const running =
    item.lifecycle_status === "connecting" ||
    item.lifecycle_status === "streaming";
  const elapsedMs = running
    ? Math.max(
        now - new Date(item.created_at).getTime(),
        item.latency_ms || 0,
        0,
      )
    : item.latency_ms;

  return (
    <Card
      className={cn(
        "rounded-2xl py-0 transition-colors hover:bg-muted/20",
        item.lifecycle_status === "failed"
          ? "border-destructive/25 bg-destructive/[0.015]"
          : "",
      )}
    >
      <div
        role="button"
        tabIndex={0}
        onClick={onOpenDetail}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onOpenDetail();
          }
        }}
        className="grid w-full min-w-0 cursor-pointer grid-cols-[minmax(0,1fr)] items-start gap-x-3.5 gap-y-3 px-4 py-4 outline-none focus-visible:ring-2 focus-visible:ring-ring/50 sm:grid-cols-[56px_minmax(0,1fr)]"
      >
        <div className="hidden size-12 items-center justify-center self-start rounded-2xl border bg-muted/40 sm:flex">
          <ModelAvatar name={primaryModelName} size={28} />
        </div>

        <div className="grid min-w-0 gap-3">
          <div className="grid gap-2.5">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <div className="min-w-0 max-w-full truncate text-[15px] font-semibold leading-6 text-foreground">
                {modelChain}
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
                value={item.channel_name || item.channel_id || "n/a"}
              />
              {item.gateway_key_id ? (
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

export function RequestsScreen() {
  const queryClient = useQueryClient();
  const { locale } = useI18n();
  const timeZone = useAppTimeZone();
  const [detailId, setDetailId] = useState<number | null>(null);
  const [attemptDetailId, setAttemptDetailId] = useState<number | null>(null);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [page, setPage] = useState(0);
  const [selectedModelPrefix, setSelectedModelPrefix] =
    useState<SelectedModelPrefix>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [protocolFilter, setProtocolFilter] = useState<"all" | ProtocolKind>(
    "all",
  );
  const [channelFilter, setChannelFilter] = useState("all");
  const [selectedGatewayKeyId, setSelectedGatewayKeyId] = useState("all");
  const [sortMode, setSortMode] = useState<SortMode>("latest");
  const [keyword, setKeyword] = useState("");
  const [clearingLogs, setClearingLogs] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const deferredKeyword = useDeferredValue(keyword.trim());

  const effectiveGatewayKeyId =
    selectedGatewayKeyId === "all" ? null : selectedGatewayKeyId;
  const statusQueryValue = statusFilter === "all" ? null : statusFilter;
  const protocolQueryValue = protocolFilter === "all" ? null : protocolFilter;
  const channelQueryValue = channelFilter === "all" ? null : channelFilter;
  const keywordQueryValue = deferredKeyword || null;

  const requestLogsQuery = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });

    if (selectedModelPrefix !== "all") {
      params.set("model_prefix", selectedModelPrefix);
    }
    if (statusQueryValue) params.set("status", statusQueryValue);
    if (protocolQueryValue) params.set("protocol", protocolQueryValue);
    if (channelQueryValue) params.set("channel", channelQueryValue);
    if (effectiveGatewayKeyId) {
      params.set("gateway_key_id", effectiveGatewayKeyId);
    }
    if (keywordQueryValue) params.set("keyword", keywordQueryValue);
    if (sortMode !== "latest") params.set("sort", sortMode);

    return `/admin/request-logs/page?${params.toString()}`;
  }, [
    channelQueryValue,
    effectiveGatewayKeyId,
    keywordQueryValue,
    page,
    protocolQueryValue,
    selectedModelPrefix,
    sortMode,
    statusQueryValue,
  ]);

  const {
    data,
    error,
    isError,
    isLoading,
    isFetching,
    refetch: refetchRequestLogs,
  } = useQuery({
    queryKey: [
      "request-logs",
      page,
      selectedModelPrefix,
      statusQueryValue,
      protocolQueryValue,
      channelQueryValue,
      effectiveGatewayKeyId,
      keywordQueryValue,
      sortMode,
    ],
    queryFn: () => apiRequest<RequestLogPage>(requestLogsQuery),
    placeholderData: keepPreviousData,
    refetchInterval: page === 0 ? 5000 : false,
  });

  const { data: gatewayApiKeys } = useQuery({
    queryKey: ["gateway-api-keys", "requests-screen"],
    queryFn: () => apiRequest<GatewayApiKey[]>("/admin/gateway-api-keys"),
    staleTime: 60_000,
  });

  const {
    data: detail,
    error: detailError,
    isError: detailIsError,
    isLoading: detailLoading,
    refetch: refetchDetail,
  } = useQuery({
    queryKey: ["request-log-detail", detailId],
    queryFn: () =>
      apiRequest<RequestLogDetail>(`/admin/request-logs/${detailId}`),
    enabled: detailId !== null,
    staleTime: 60_000,
    gcTime: REQUEST_LOG_DETAIL_GC_TIME,
  });

  const {
    data: attemptDetail,
    error: attemptDetailError,
    isError: attemptDetailIsError,
    isLoading: attemptDetailLoading,
    refetch: refetchAttemptDetail,
  } = useQuery({
    queryKey: ["request-log-attempt-detail", attemptDetailId],
    queryFn: () =>
      apiRequest<RequestLogDetail>(`/admin/request-logs/${attemptDetailId}`),
    enabled: attemptDetailId !== null,
    staleTime: 60_000,
    gcTime: REQUEST_LOG_DETAIL_GC_TIME,
  });

  const modelPrefixOptions = useMemo(() => {
    const optionsByPrefix = new Map<string, ModelPrefixOption>();
    for (const model of data?.model_names ?? []) {
      const prefix = getModelFamilyKey(model);
      if (prefix && !optionsByPrefix.has(prefix)) {
        optionsByPrefix.set(prefix, {
          key: prefix,
          label: getModelFamilyLabel(model),
          sampleModel: model,
        });
      }
    }

    return [
      {
        key: "all" as const,
        label: titleForLocale(locale, "全部", "All"),
        sampleModel: "all",
      },
      ...Array.from(optionsByPrefix.values()).sort((a, b) =>
        a.label.localeCompare(b.label),
      ),
    ];
  }, [data?.model_names, locale]);

  const visibleData = data?.items ?? [];
  const showModelPrefixFilter = modelPrefixOptions.length > 1;
  const effectiveSelectedModelPrefix = modelPrefixOptions.some(
    (item) => item.key === selectedModelPrefix,
  )
    ? selectedModelPrefix
    : "all";

  const channelOptions = useMemo(() => {
    const items = data?.channels ?? [];
    if (channelQueryValue && !items.includes(channelQueryValue)) {
      return [channelQueryValue, ...items];
    }
    return items;
  }, [channelQueryValue, data?.channels]);

  const gatewayKeyOptions = useMemo(() => {
    const items = (gatewayApiKeys ?? []).map((item) => ({
      id: item.id,
      label: formatGatewayKeyOptionLabel(item),
    }));
    if (
      effectiveGatewayKeyId &&
      !items.some((item) => item.id === effectiveGatewayKeyId)
    ) {
      items.unshift({
        id: effectiveGatewayKeyId,
        label: shortenGatewayKeyId(effectiveGatewayKeyId),
      });
    }
    return items;
  }, [effectiveGatewayKeyId, gatewayApiKeys]);

  const total = data?.total ?? 0;
  const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1);
  const hasNextPage = page < totalPages - 1;
  const paginationItems = buildPaginationItems(page + 1, totalPages);
  const activeFilterCount = [
    selectedModelPrefix !== "all",
    statusFilter !== "all",
    protocolFilter !== "all",
    channelFilter !== "all",
    effectiveGatewayKeyId !== null,
    Boolean(keyword.trim()),
  ].filter(Boolean).length;

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (selectedModelPrefix !== effectiveSelectedModelPrefix) {
      setSelectedModelPrefix(effectiveSelectedModelPrefix);
    }
  }, [effectiveSelectedModelPrefix, selectedModelPrefix]);

  useEffect(() => {
    if (!isError) return;
    toast.error(
      titleForLocale(locale, "请求日志加载失败", "Failed to load request logs"),
      {
        id: "request-logs-load-error",
        description:
          error instanceof Error
            ? error.message
            : titleForLocale(
                locale,
                "无法读取请求日志",
                "Unable to read request logs",
              ),
      },
    );
  }, [error, isError, locale]);

  useEffect(() => {
    function handleScroll() {
      setShowBackToTop(window.scrollY > 320);
    }

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  async function refreshLogs() {
    await Promise.all([
      refetchRequestLogs(),
      detailId !== null ? refetchDetail() : Promise.resolve(),
      attemptDetailId !== null ? refetchAttemptDetail() : Promise.resolve(),
    ]);
  }

  async function clearRequestLogs() {
    const confirmed = window.confirm(
      titleForLocale(
        locale,
        "确认删除全部请求日志？",
        "Delete all request logs?",
      ),
    );
    if (!confirmed) return;

    setClearingLogs(true);
    try {
      await apiRequest<void>("/admin/request-logs", { method: "DELETE" });
      setPage(0);
      setDetailId(null);
      setAttemptDetailId(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["request-logs"] }),
        queryClient.invalidateQueries({ queryKey: ["overview"] }),
        queryClient.invalidateQueries({ queryKey: ["overview-dashboard"] }),
        queryClient.invalidateQueries({ queryKey: ["overview-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["overview-daily"] }),
        queryClient.invalidateQueries({ queryKey: ["overview-models"] }),
        queryClient.invalidateQueries({ queryKey: ["overview-logs"] }),
        queryClient.invalidateQueries({ queryKey: ["gateway-api-keys"] }),
      ]);
      toast.success(
        titleForLocale(locale, "请求日志已清空", "Request logs cleared"),
      );
    } catch (requestError) {
      toast.error(
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(
              locale,
              "清空请求日志失败",
              "Failed to clear request logs",
            ),
      );
    } finally {
      setClearingLogs(false);
    }
  }

  function handleModelPrefixChange(value: SelectedModelPrefix) {
    setSelectedModelPrefix(value);
    setPage(0);
  }

  function handleStatusChange(value: StatusFilter) {
    setStatusFilter(value);
    setPage(0);
  }

  function handleProtocolChange(value: "all" | ProtocolKind) {
    setProtocolFilter(value);
    setPage(0);
  }

  function handleChannelChange(value: string) {
    setChannelFilter(value);
    setPage(0);
  }

  function handleGatewayKeyChange(value: string) {
    setSelectedGatewayKeyId(value);
    setPage(0);
  }

  function handleSortChange(value: SortMode) {
    setSortMode(value);
    setPage(0);
  }

  function handleKeywordChange(value: string) {
    setKeyword(value);
    setPage(0);
  }

  function resetFilters() {
    setSelectedModelPrefix("all");
    setStatusFilter("all");
    setProtocolFilter("all");
    setChannelFilter("all");
    setSelectedGatewayKeyId("all");
    setSortMode("latest");
    setKeyword("");
    setPage(0);
  }

  return (
    <TooltipProvider>
      <section className="flex flex-col gap-4 md:gap-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-foreground">
              {titleForLocale(locale, "请求日志", "Requests")}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 self-start lg:self-auto">
            <Button
              type="button"
              variant="outline"
              onClick={() => void refreshLogs()}
              disabled={isFetching}
            >
              <RefreshCcw
                data-icon="inline-start"
                className={cn(isFetching && "animate-spin")}
              />
              {titleForLocale(locale, "刷新", "Refresh")}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={resetFilters}
              disabled={!activeFilterCount && sortMode === "latest"}
            >
              <RotateCcw data-icon="inline-start" />
              {titleForLocale(locale, "重置", "Reset")}
            </Button>
          </div>
        </div>

        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,4fr)_320px]">
          <div className="order-2 grid gap-4 xl:order-1">
            {showModelPrefixFilter ? (
              <div className="rounded-2xl border bg-card px-4 py-3 sm:px-5 sm:py-4">
                <div className="flex items-center justify-between gap-3 sm:mb-3">
                  <div className="text-base font-semibold text-foreground">
                    {titleForLocale(
                      locale,
                      "选择模型系列",
                      "Choose model series",
                    )}
                  </div>
                </div>

                <NativeSelect
                  className="mt-3 w-full sm:hidden"
                  value={effectiveSelectedModelPrefix}
                  onChange={(event) =>
                    handleModelPrefixChange(event.target.value)
                  }
                >
                  {modelPrefixOptions.map((option) => (
                    <NativeSelectOption key={option.key} value={option.key}>
                      {option.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>

                <div className="hidden snap-x gap-3 overflow-x-auto pb-1 sm:flex">
                  {modelPrefixOptions.map((option) => (
                    <SeriesChip
                      key={option.key}
                      selected={effectiveSelectedModelPrefix === option.key}
                      label={option.label}
                      sampleModel={option.sampleModel}
                      isAll={option.key === "all"}
                      onClick={() => handleModelPrefixChange(option.key)}
                    />
                  ))}
                </div>
              </div>
            ) : null}

            <div className="rounded-2xl border bg-card p-3 sm:p-4">
              {isLoading ? (
                <p className="px-2 py-6 text-sm text-muted-foreground">
                  {titleForLocale(
                    locale,
                    "正在加载请求日志...",
                    "Loading request logs...",
                  )}
                </p>
              ) : null}

              {!isError && !isLoading && visibleData.length === 0 ? (
                <div className="rounded-xl border border-dashed bg-background px-6 py-14 text-center text-sm text-muted-foreground">
                  {activeFilterCount
                    ? titleForLocale(
                        locale,
                        "当前筛选条件下没有请求日志。",
                        "No request logs match the current filters.",
                      )
                    : titleForLocale(
                        locale,
                        "暂无请求日志。",
                        "No request logs yet.",
                      )}
                </div>
              ) : null}

              {visibleData.length ? (
                <div className="flex flex-col gap-3">
                  {visibleData.map((item) => (
                    <RequestCard
                      key={item.id}
                      item={item}
                      locale={locale}
                      timeZone={timeZone}
                      now={now}
                      onOpenDetail={() => setDetailId(item.id)}
                      onOpenAttempts={() => setAttemptDetailId(item.id)}
                    />
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <aside className="order-1 xl:order-2">
            <div className="rounded-2xl border bg-card p-4 xl:sticky xl:top-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="inline-flex size-9 items-center justify-center rounded-xl bg-primary/[0.08] text-primary">
                    <Filter size={16} />
                  </span>
                  <div>
                    <div className="text-sm font-semibold text-foreground">
                      {titleForLocale(locale, "筛选", "Filters")}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {locale === "zh-CN"
                        ? `已启用 ${activeFilterCount} 项`
                        : `${activeFilterCount} active`}
                    </div>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={resetFilters}
                  disabled={!activeFilterCount && sortMode === "latest"}
                >
                  {titleForLocale(locale, "清空", "Clear")}
                </Button>
              </div>

              <div>
                <FieldSet className="gap-4">
                  <FieldLegend>
                    {titleForLocale(locale, "筛选条件", "Refine results")}
                  </FieldLegend>
                  <FieldGroup className="gap-4">
                    <Field>
                      <FieldLabel>
                        {titleForLocale(locale, "关键词", "Keyword")}
                      </FieldLabel>
                      <ToolbarSearchInput
                        value={keyword}
                        onChange={handleKeywordChange}
                        onClear={() => handleKeywordChange("")}
                        placeholder={titleForLocale(
                          locale,
                          "模型 / 渠道 / API Key / 错误 / 状态码",
                          "Model / channel / API key / error / status",
                        )}
                        className="max-w-none"
                      />
                    </Field>

                    <Field>
                      <FieldLabel>
                        {titleForLocale(locale, "状态", "Status")}
                      </FieldLabel>
                      <div className="grid grid-cols-2 gap-2">
                        {[
                          {
                            key: "all" as const,
                            label: titleForLocale(locale, "全部", "All"),
                          },
                          {
                            key: "running" as const,
                            label: titleForLocale(locale, "进行中", "Running"),
                          },
                          {
                            key: "success" as const,
                            label: titleForLocale(locale, "成功", "Success"),
                          },
                          {
                            key: "failed" as const,
                            label: titleForLocale(locale, "失败", "Failed"),
                          },
                        ].map((option) => (
                          <Button
                            key={option.key}
                            type="button"
                            variant={
                              statusFilter === option.key
                                ? "default"
                                : "outline"
                            }
                            size="sm"
                            onClick={() => handleStatusChange(option.key)}
                          >
                            {option.label}
                          </Button>
                        ))}
                      </div>
                    </Field>

                    <Field>
                      <FieldLabel htmlFor="request-log-protocol">
                        {titleForLocale(locale, "协议", "Protocol")}
                      </FieldLabel>
                      <NativeSelect
                        id="request-log-protocol"
                        className="w-full"
                        value={protocolFilter}
                        onChange={(event) =>
                          handleProtocolChange(
                            event.target.value as "all" | ProtocolKind,
                          )
                        }
                      >
                        <NativeSelectOption value="all">
                          {titleForLocale(locale, "全部协议", "All protocols")}
                        </NativeSelectOption>
                        <NativeSelectOption value="openai_chat">
                          OpenAI Chat
                        </NativeSelectOption>
                        <NativeSelectOption value="openai_responses">
                          OpenAI Responses
                        </NativeSelectOption>
                        <NativeSelectOption value="openai_embedding">
                          OpenAI Embedding
                        </NativeSelectOption>
                        <NativeSelectOption value="rerank">
                          Rerank
                        </NativeSelectOption>
                        <NativeSelectOption value="anthropic">
                          Anthropic
                        </NativeSelectOption>
                        <NativeSelectOption value="gemini">
                          Gemini
                        </NativeSelectOption>
                      </NativeSelect>
                    </Field>

                    <Field>
                      <FieldLabel htmlFor="request-log-channel">
                        {titleForLocale(locale, "渠道", "Channel")}
                      </FieldLabel>
                      <NativeSelect
                        id="request-log-channel"
                        className="w-full"
                        value={channelFilter}
                        onChange={(event) =>
                          handleChannelChange(event.target.value)
                        }
                      >
                        <NativeSelectOption value="all">
                          {titleForLocale(locale, "全部渠道", "All channels")}
                        </NativeSelectOption>
                        {channelOptions.map((channel) => (
                          <NativeSelectOption key={channel} value={channel}>
                            {channel}
                          </NativeSelectOption>
                        ))}
                      </NativeSelect>
                    </Field>

                    <Field>
                      <FieldLabel htmlFor="request-log-gateway-key">
                        API Key
                      </FieldLabel>
                      <NativeSelect
                        id="request-log-gateway-key"
                        className="w-full"
                        value={selectedGatewayKeyId}
                        onChange={(event) =>
                          handleGatewayKeyChange(event.target.value)
                        }
                      >
                        <NativeSelectOption value="all">
                          {titleForLocale(
                            locale,
                            "全部 API Key",
                            "All API keys",
                          )}
                        </NativeSelectOption>
                        {gatewayKeyOptions.map((item) => (
                          <NativeSelectOption key={item.id} value={item.id}>
                            {item.label}
                          </NativeSelectOption>
                        ))}
                      </NativeSelect>
                    </Field>

                    <Field>
                      <FieldLabel htmlFor="request-log-sort">
                        {titleForLocale(locale, "排序", "Sort by")}
                      </FieldLabel>
                      <NativeSelect
                        id="request-log-sort"
                        className="w-full"
                        value={sortMode}
                        onChange={(event) =>
                          handleSortChange(event.target.value as SortMode)
                        }
                      >
                        <NativeSelectOption value="latest">
                          {titleForLocale(locale, "最新优先", "Latest first")}
                        </NativeSelectOption>
                        <NativeSelectOption value="cost">
                          {titleForLocale(locale, "费用优先", "Highest cost")}
                        </NativeSelectOption>
                        <NativeSelectOption value="latency">
                          {titleForLocale(
                            locale,
                            "耗时优先",
                            "Longest latency",
                          )}
                        </NativeSelectOption>
                        <NativeSelectOption value="tokens">
                          {titleForLocale(locale, "Token 优先", "Most tokens")}
                        </NativeSelectOption>
                      </NativeSelect>
                    </Field>
                  </FieldGroup>
                </FieldSet>
                <div className="mt-4 border-t pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full text-destructive hover:text-destructive"
                    onClick={() => void clearRequestLogs()}
                    disabled={clearingLogs}
                  >
                    <Trash2 data-icon="inline-start" />
                    {clearingLogs
                      ? titleForLocale(locale, "清空中...", "Clearing...")
                      : titleForLocale(
                          locale,
                          "清空请求日志",
                          "Clear request logs",
                        )}
                  </Button>
                </div>
              </div>
            </div>
          </aside>
        </div>

        {totalPages > 1 ? (
          <Pagination id="requests-pagination" className="justify-center pt-1">
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  href="#requests-pagination"
                  text={titleForLocale(locale, "上一页", "Prev")}
                  onClick={(event) => {
                    event.preventDefault();
                    if (page === 0) return;
                    setPage((current) => Math.max(current - 1, 0));
                  }}
                  className={cn(page === 0 && "pointer-events-none opacity-50")}
                />
              </PaginationItem>
              {paginationItems.map((item, index) => (
                <PaginationItem key={`${item}-${index}`}>
                  {item === "ellipsis" ? (
                    <PaginationEllipsis />
                  ) : (
                    <PaginationLink
                      href="#requests-pagination"
                      size="default"
                      isActive={item === page + 1}
                      onClick={(event) => {
                        event.preventDefault();
                        if (item === page + 1) return;
                        setPage(item - 1);
                      }}
                    >
                      {item}
                    </PaginationLink>
                  )}
                </PaginationItem>
              ))}

              <PaginationItem>
                <PaginationNext
                  href="#requests-pagination"
                  text={titleForLocale(locale, "下一页", "Next")}
                  onClick={(event) => {
                    event.preventDefault();
                    if (!hasNextPage) return;
                    setPage((current) => current + 1);
                  }}
                  className={cn(
                    !hasNextPage && "pointer-events-none opacity-50",
                  )}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        ) : null}

        <Dialog
          open={detailId !== null}
          onOpenChange={(open) => {
            if (!open) setDetailId(null);
          }}
        >
          <AppDialogContent
            className="max-w-6xl"
            title={titleForLocale(locale, "日志详情", "Log detail")}
          >
            {detailIsError ? (
              <Alert variant="destructive">
                <AlertCircle />
                <AlertTitle>
                  {titleForLocale(
                    locale,
                    "详情加载失败",
                    "Failed to load detail",
                  )}
                </AlertTitle>
                <AlertDescription>
                  {detailError instanceof Error
                    ? detailError.message
                    : titleForLocale(
                        locale,
                        "无法读取日志详情",
                        "Unable to read log detail",
                      )}
                </AlertDescription>
              </Alert>
            ) : detailLoading || !detail ? (
              <div className="rounded-md border bg-background px-5 py-8 text-sm text-muted-foreground">
                {titleForLocale(locale, "正在加载详情...", "Loading detail...")}
              </div>
            ) : (
              <div className="grid min-h-[60dvh] overflow-hidden sm:min-h-[560px] xl:grid-cols-2">
                <JsonViewer
                  key={`request-${detail.id}`}
                  title={titleForLocale(locale, "请求内容", "Request")}
                  content={detail.request_content}
                  emptyText={titleForLocale(
                    locale,
                    "无输入内容",
                    "No request content",
                  )}
                  locale={locale}
                />
                <JsonViewer
                  key={`response-${detail.id}`}
                  className="border-t xl:border-t-0 xl:border-l"
                  title={titleForLocale(locale, "响应内容", "Response")}
                  content={detail.response_content}
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
            if (!open) setAttemptDetailId(null);
          }}
        >
          <AppDialogContent
            className="max-w-4xl"
            title={titleForLocale(locale, "尝试链路", "Attempts")}
          >
            {attemptDetailIsError ? (
              <Alert variant="destructive">
                <AlertCircle />
                <AlertTitle>
                  {titleForLocale(
                    locale,
                    "尝试链路加载失败",
                    "Failed to load attempts",
                  )}
                </AlertTitle>
                <AlertDescription>
                  {attemptDetailError instanceof Error
                    ? attemptDetailError.message
                    : titleForLocale(
                        locale,
                        "无法读取尝试链路",
                        "Unable to read attempts",
                      )}
                </AlertDescription>
              </Alert>
            ) : attemptDetailLoading || !attemptDetail ? (
              <div className="rounded-md border bg-background px-5 py-8 text-sm text-muted-foreground">
                {titleForLocale(
                  locale,
                  "正在加载尝试链路...",
                  "Loading attempts...",
                )}
              </div>
            ) : (
              <div className="grid gap-4">
                {formatErrorDisplay(attemptDetail.error_message) ? (
                  <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-4 text-sm text-destructive">
                    <div className="flex items-start gap-3">
                      <AlertCircle size={16} className="mt-0.5 shrink-0" />
                      <span className="whitespace-pre-wrap break-words">
                        {formatErrorDisplay(attemptDetail.error_message)}
                      </span>
                    </div>
                  </div>
                ) : null}
                <AttemptChain detail={attemptDetail} locale={locale} />
              </div>
            )}
          </AppDialogContent>
        </Dialog>

        {showBackToTop ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="icon-lg"
                className="fixed right-4 bottom-4 z-40 rounded-full shadow-sm sm:right-6 sm:bottom-6"
                onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              >
                <ArrowUp />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">
              {titleForLocale(locale, "返回顶部", "Back to top")}
            </TooltipContent>
          </Tooltip>
        ) : null}

        <style jsx global>{`
          .json-view-shell .w-rjv-inner > span,
          .json-view-shell .w-rjv-line,
          .json-view-shell .w-rjv-inner > div:not(.w-rjv-wrap) {
            min-height: 1.5rem;
            line-height: 1.5rem;
          }

          .json-view-shell .w-rjv-inner > span {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
          }
        `}</style>
      </section>
    </TooltipProvider>
  );
}
