"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import dynamic from "next/dynamic";
import { CheckCheck, Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { titleForLocale } from "@/lib/I18nContext";
import { cn } from "@/lib/utils";
import { tryParseJsonValue, type JsonLike } from "./requestLogUtils";

const JsonView = dynamic(() => import("@uiw/react-json-view"), {
  ssr: false,
});

export function normalizeLineBreaks(value: string) {
  return value.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

export type JsonContainer = JsonLike[] | { [key: string]: JsonLike };
export type ParsedViewerContent =
  | { isJson: true; data: JsonContainer }
  | { isJson: false; data: string };

export const JSON_VIEW_STYLE = {
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

export function parseViewerContent(content: string): ParsedViewerContent {
  const parsed = tryParseJsonValue(content);
  if (parsed && typeof parsed === "object") {
    return { isJson: true, data: parsed };
  }
  return { isJson: false, data: content };
}

export function getJsonLineHeights(root: HTMLElement | null) {
  if (!root) return [];

  const lineNodes = root.querySelectorAll<HTMLElement>(
    ".w-rjv-inner > span, .w-rjv-line, .w-rjv-inner > div:not(.w-rjv-wrap)",
  );

  return Array.from(lineNodes, (node) =>
    Math.max(Math.round(node.getBoundingClientRect().height), 24),
  );
}

export function lineHeightsEqual(a: number[], b: number[]) {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

export function LineNumbersColumn({ lineHeights }: { lineHeights: number[] }) {
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

export function LineNumberedCode({ text }: { text: string }) {
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

/** Render a request payload as structured JSON or line-numbered text. */
export function RequestPayloadViewer({
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
