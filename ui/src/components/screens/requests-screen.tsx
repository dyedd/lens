"use client"

import { useDeferredValue, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import JsonView from '@uiw/react-json-view'
import {
  AlertCircle,
  ArrowDownToLine,
  ArrowUp,
  ArrowUpFromLine,
  ChevronDown,
  CheckCheck,
  Clock3,
  Copy,
  Database,
  DollarSign,
  Filter,
  KeyRound,
  LayoutGrid,
  RefreshCcw,
  RotateCcw,
  ServerCog,
  Trash2,
  Upload,
  Waypoints,
  Zap,
} from 'lucide-react'
import { ApiError, GatewayApiKey, OverviewModelAnalytics, ProtocolKind, RequestLogDetail, RequestLogItem, RequestLogPage, apiRequest } from '@/lib/api'
import { formatLogDateTime } from '@/lib/datetime'
import { useAppTimeZone } from '@/hooks/use-app-time-zone'
import { useI18n } from '@/lib/i18n'
import { ModelAvatar } from '@/lib/model-icons'
import { cn } from '@/lib/utils'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field, FieldGroup, FieldLabel, FieldLegend, FieldSet } from '@/components/ui/field'
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from '@/components/ui/item'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { ToolbarSearchInput } from '@/components/ui/toolbar-search-input'

const PAGE_SIZE = 20
const DETAIL_PREFETCH_HOVER_DELAY_MS = 120

const MODEL_SERIES_PRESETS = [
  {
    key: 'openai',
    zh: 'OpenAI',
    en: 'OpenAI',
    sampleModel: 'gpt-5.4',
    prefixes: ['gpt-', 'o1', 'o3', 'o4', 'chatgpt', 'openai'],
  },
  {
    key: 'claude',
    zh: 'Claude',
    en: 'Claude',
    sampleModel: 'claude-opus-4-6',
    prefixes: ['claude', 'anthropic'],
  },
  {
    key: 'gemini',
    zh: 'Gemini',
    en: 'Gemini',
    sampleModel: 'gemini-2.5-pro',
    prefixes: ['gemini', 'gemma', 'google'],
  },
  {
    key: 'deepseek',
    zh: 'DeepSeek',
    en: 'DeepSeek',
    sampleModel: 'deepseek-v3',
    prefixes: ['deepseek'],
  },
  {
    key: 'qwen',
    zh: 'Qwen',
    en: 'Qwen',
    sampleModel: 'qwen-max',
    prefixes: ['qwen', 'qwq', 'alibaba'],
  },
  {
    key: 'kimi',
    zh: 'Kimi',
    en: 'Kimi',
    sampleModel: 'kimi-k2',
    prefixes: ['moonshot', 'kimi'],
  },
  {
    key: 'glm',
    zh: 'GLM',
    en: 'GLM',
    sampleModel: 'glm-4.5',
    prefixes: ['glm', 'chatglm', 'zhipu', 'z-ai'],
  },
  {
    key: 'minimax',
    zh: 'MiniMax',
    en: 'MiniMax',
    sampleModel: 'minimax-text-01',
    prefixes: ['minimax', 'abab', 'minmax'],
  },
  {
    key: 'other',
    zh: '其他',
    en: 'Other',
    sampleModel: 'other',
    prefixes: [],
  },
] as const

type ModelSeriesKey = typeof MODEL_SERIES_PRESETS[number]['key']
type SelectedSeries = 'all' | ModelSeriesKey
type StatusFilter = 'all' | 'success' | 'failed'
type SortMode = 'latest' | 'cost' | 'latency' | 'tokens'
type JsonLike = null | boolean | number | string | JsonLike[] | { [key: string]: JsonLike }

function formatMs(value: number) {
  if (value < 1000) return `${value} ms`
  return `${(value / 1000).toFixed(2)} s`
}

function formatMoney(value: number) {
  return `$${value.toFixed(6)}`
}

function formatCount(value: number) {
  return value.toLocaleString()
}

function shortenGatewayKeyId(value?: string | null) {
  if (!value) return ''
  if (value.length <= 10) return value
  return `${value.slice(0, 4)}...${value.slice(-4)}`
}

function formatGatewayKeyLabel(
  item: Pick<RequestLogItem, 'gateway_key_id' | 'gateway_key_remark'>,
  locale: 'zh-CN' | 'en-US'
) {
  return item.gateway_key_remark?.trim() || shortenGatewayKeyId(item.gateway_key_id) || (locale === 'zh-CN' ? '未绑定 API Key' : 'No API key')
}

function formatGatewayKeyOptionLabel(item: Pick<GatewayApiKey, 'id' | 'remark'>) {
  return item.remark.trim() || shortenGatewayKeyId(item.id)
}

function tryParseJsonValue(value: string) {
  try {
    return JSON.parse(value) as JsonLike
  } catch {
    return null
  }
}

function formatHtmlErrorContent(value: string) {
  return value
    .replace(/>\s*</g, '>\n<')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|section|article|header|footer|main|h1|h2|h3|h4|h5|h6|li|ul|ol|pre|code)>/gi, '$&\n')
    .trim()
}

function formatJsonErrorContent(prefix: string, value: JsonLike) {
  const jsonText = JSON.stringify(value, null, 2)
  if (!jsonText) return prefix.trim() || null
  return jsonText
}

function formatErrorDisplay(value: string | null | undefined) {
  const raw = value?.trim()
  if (!raw) return null

  const directParsed = tryParseJsonValue(raw)
  if (directParsed !== null) {
    return formatJsonErrorContent('', directParsed)
  }

  const jsonStart = raw.indexOf('{')
  if (jsonStart > 0) {
    const nestedParsed = tryParseJsonValue(raw.slice(jsonStart))
    if (nestedParsed !== null) {
      return formatJsonErrorContent(raw.slice(0, jsonStart), nestedParsed)
    }
  }

  if (/<!doctype html|<html|<head|<body|<title/i.test(raw)) {
    return formatHtmlErrorContent(raw)
  }

  return raw
}

function getResolvedGroupName(item: Pick<RequestLogItem, 'requested_group_name' | 'resolved_group_name' | 'upstream_model_name'>) {
  return item.resolved_group_name || item.requested_group_name || item.upstream_model_name || 'n/a'
}

function getModelChain(item: Pick<RequestLogItem, 'requested_group_name' | 'resolved_group_name' | 'upstream_model_name'>) {
  const requested = item.requested_group_name?.trim()
  const resolved = item.resolved_group_name?.trim()
  if (requested && resolved && requested !== resolved) {
    return `${requested} -> ${resolved}`
  }
  return resolved || requested || item.upstream_model_name || 'n/a'
}

function getSecondaryModelName(item: Pick<RequestLogItem, 'requested_group_name' | 'resolved_group_name' | 'upstream_model_name'>) {
  const resolved = item.resolved_group_name?.trim()
  const upstream = item.upstream_model_name?.trim()
  if (upstream && upstream !== resolved) {
    return upstream
  }
  return null
}

function normalizeModelName(value: string | null | undefined) {
  return (value || '').trim().toLowerCase()
}

function getSeriesPreset(name: string) {
  const normalized = normalizeModelName(name)
  return MODEL_SERIES_PRESETS.find((item) => item.key !== 'other' && item.prefixes.some((prefix) => normalized.startsWith(prefix))) ?? MODEL_SERIES_PRESETS.find((item) => item.key === 'other')!
}

function getSeriesKey(item: Pick<RequestLogItem, 'requested_group_name' | 'resolved_group_name' | 'upstream_model_name'>): ModelSeriesKey {
  return getSeriesPreset(getResolvedGroupName(item)).key
}

function buildPaginationItems(currentPage: number, totalPages: number) {
  if (totalPages <= 1) return [1]
  if (totalPages <= 5) return Array.from({ length: totalPages }, (_, index) => index + 1)

  if (currentPage <= 1) {
    return [1, 2, 3, 'ellipsis', totalPages] as const
  }

  if (currentPage >= totalPages - 2) {
    return [1, 'ellipsis', totalPages - 2, totalPages - 1, totalPages] as const
  }

  return [1, currentPage, currentPage + 1, currentPage + 2, 'ellipsis', totalPages] as const
}

function StatusBadge({
  success,
  locale,
  errorMessage,
}: {
  success: boolean
  locale: 'zh-CN' | 'en-US'
  errorMessage?: string | null
}) {
  const content = (
    <Badge
      variant="outline"
      className={cn(
        'rounded-full border-0 px-3 py-1 text-xs font-medium',
        success ? 'bg-primary/10 text-primary' : 'bg-destructive/12 text-destructive'
      )}
    >
      {success ? (locale === 'zh-CN' ? '成功' : 'Success') : (locale === 'zh-CN' ? '失败' : 'Failed')}
    </Badge>
  )

  if (success || !errorMessage?.trim()) {
    return content
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex">{content}</span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm whitespace-pre-wrap break-words" side="bottom">
        {errorMessage}
      </TooltipContent>
    </Tooltip>
  )
}

function StatusCodeBadge({
  statusCode,
}: {
  statusCode: number | null | undefined
}) {
  return (
    <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-medium">
      {statusCode ?? '-'}
    </Badge>
  )
}

function ProtocolBadge({ protocol }: { protocol: RequestLogItem['protocol'] }) {
  const labelMap = {
    openai_chat: 'chat',
    openai_responses: 'responses',
    anthropic: 'anthropic',
    gemini: 'gemini',
  } as const

  return (
    <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-medium">
      {labelMap[protocol] ?? protocol}
    </Badge>
  )
}

function normalizeLineBreaks(value: string) {
  return value.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
}

type JsonContainer = JsonLike[] | { [key: string]: JsonLike }
type ParsedViewerContent =
  | { isJson: true; data: JsonContainer }
  | { isJson: false; data: string }

const JSON_VIEW_STYLE = {
  fontSize: '12px',
  fontFamily: 'var(--font-mono), ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
  backgroundColor: 'transparent',
  '--w-rjv-background-color': 'transparent',
  '--w-rjv-font-family': 'var(--font-mono), ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
  '--w-rjv-color': 'var(--foreground)',
  '--w-rjv-key-number': 'var(--primary)',
  '--w-rjv-key-string': 'var(--primary)',
  '--w-rjv-line-color': 'var(--border)',
  '--w-rjv-arrow-color': 'var(--muted-foreground)',
  '--w-rjv-info-color': 'var(--muted-foreground)',
  '--w-rjv-curlybraces-color': 'var(--foreground)',
  '--w-rjv-colon-color': 'var(--muted-foreground)',
  '--w-rjv-brackets-color': 'var(--foreground)',
  '--w-rjv-ellipsis-color': 'var(--muted-foreground)',
  '--w-rjv-quotes-color': 'var(--muted-foreground)',
  '--w-rjv-quotes-string-color': 'var(--chart-2)',
  '--w-rjv-type-string-color': 'var(--chart-2)',
  '--w-rjv-type-int-color': 'var(--chart-4)',
  '--w-rjv-type-float-color': 'var(--chart-4)',
  '--w-rjv-type-bigint-color': 'var(--chart-4)',
  '--w-rjv-type-boolean-color': 'var(--chart-3)',
  '--w-rjv-type-null-color': 'var(--muted-foreground)',
  '--w-rjv-type-undefined-color': 'var(--muted-foreground)',
} as CSSProperties

function parseViewerContent(content: string): ParsedViewerContent {
  try {
    const parsed = JSON.parse(content) as JsonLike
    if (parsed && typeof parsed === 'object') {
      return { isJson: true, data: parsed }
    }
  } catch {
    return { isJson: false, data: content }
  }
  return { isJson: false, data: content }
}

function getJsonLineHeights(root: HTMLElement | null) {
  if (!root) {
    return []
  }

  const lineNodes = root.querySelectorAll<HTMLElement>(
    '.w-rjv-inner > span, .w-rjv-line, .w-rjv-inner > div:not(.w-rjv-wrap)'
  )

  return Array.from(lineNodes, (node) => Math.max(Math.round(node.getBoundingClientRect().height), 24))
}

function lineHeightsEqual(a: number[], b: number[]) {
  return a.length === b.length && a.every((value, index) => value === b[index])
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
  )
}

function LineNumberedCode({ text }: { text: string }) {
  const lines = useMemo(() => normalizeLineBreaks(text).split('\n'), [text])

  return (
    <div className="max-h-[60dvh] overflow-auto sm:max-h-[560px]">
      <div className="min-w-full py-3">
        {lines.map((line, index) => (
          <div key={index} className="grid grid-cols-[44px_minmax(0,1fr)] font-mono text-xs leading-6">
            <div className="select-none border-r bg-muted/20 pr-3 text-right text-[11px] text-muted-foreground/70">
              {index + 1}
            </div>
            <pre className="m-0 min-w-0 whitespace-pre-wrap break-words px-4 text-foreground">{line || ' '}</pre>
          </div>
        ))}
      </div>
    </div>
  )
}

function JsonViewer({
  title,
  content,
  emptyText,
  locale,
  className,
}: {
  title: string
  content?: string | null
  emptyText: string
  locale: 'zh-CN' | 'en-US'
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [ready, setReady] = useState(false)
  const [lineHeights, setLineHeights] = useState<number[]>([])
  const jsonViewRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!content) {
      return
    }

    const timer = window.setTimeout(() => setReady(true), 80)
    return () => window.clearTimeout(timer)
  }, [content])

  async function copyContent() {
    if (!content) return
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      toast.success(locale === 'zh-CN' ? '已复制内容' : 'Copied content')
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error(locale === 'zh-CN' ? '复制失败' : 'Failed to copy')
    }
  }

  const parsed = useMemo(() => {
    if (!ready || !content) {
      return null
    }
    return parseViewerContent(content)
  }, [content, ready])

  useEffect(() => {
    if (!parsed?.isJson || !jsonViewRef.current) {
      return
    }

    const root = jsonViewRef.current
    let frameId = 0

    const measure = () => {
      frameId = 0
      const next = getJsonLineHeights(root)
      setLineHeights((current) => lineHeightsEqual(current, next) ? current : next)
    }

    const scheduleMeasure = () => {
      if (frameId) {
        window.cancelAnimationFrame(frameId)
      }
      frameId = window.requestAnimationFrame(measure)
    }

    scheduleMeasure()

    const mutationObserver = new MutationObserver(() => scheduleMeasure())
    mutationObserver.observe(root, {
      childList: true,
      subtree: true,
      characterData: true,
    })

    const resizeObserver = new ResizeObserver(() => scheduleMeasure())
    resizeObserver.observe(root)

    return () => {
      if (frameId) {
        window.cancelAnimationFrame(frameId)
      }
      mutationObserver.disconnect()
      resizeObserver.disconnect()
    }
  }, [parsed])

  return (
    <section className={cn("flex min-h-[60dvh] min-w-0 flex-col bg-background sm:min-h-[560px]", className)}>
      <header className="flex shrink-0 flex-col items-start justify-between gap-3 px-3 py-3 sm:flex-row sm:items-center sm:px-4">
        <div className="text-sm font-semibold text-foreground">{title}</div>
        <div className="flex flex-wrap items-center gap-2">
          {parsed?.isJson ? (
            <Button type="button" variant="ghost" size="sm" onClick={() => setExpanded((current) => !current)}>
              {expanded ? (locale === 'zh-CN' ? '折叠' : 'Collapse') : (locale === 'zh-CN' ? '展开' : 'Expand')}
            </Button>
          ) : null}
          <Button type="button" variant="ghost" size="sm" onClick={() => void copyContent()} disabled={!content}>
            {copied ? <CheckCheck data-icon="inline-start" /> : <Copy data-icon="inline-start" />}
            {locale === 'zh-CN' ? '复制' : 'Copy'}
          </Button>
        </div>
      </header>

      <div className="min-h-0 flex-1">
        {!content ? (
          <div className="px-4 py-6 text-xs text-muted-foreground">{emptyText}</div>
        ) : !ready ? (
          <div className="px-4 py-6 text-xs text-muted-foreground">
            {locale === 'zh-CN' ? '正在准备内容...' : 'Preparing content...'}
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
  )
}

function RequestMetric({
  icon,
  label,
  value,
  valueClassName,
}: {
  icon: React.ReactNode
  label: string
  value: string
  valueClassName?: string
}) {
  return (
    <div className="flex min-h-[58px] min-w-0 items-start gap-2.5 rounded-xl border bg-background px-3 py-2.5">
      <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-muted/35 text-muted-foreground">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[11px] leading-4 text-muted-foreground">{label}</div>
        <div className={cn('mt-1 whitespace-normal break-words text-[13px] font-semibold leading-4 text-foreground tabular-nums', valueClassName)}>{value}</div>
      </div>
    </div>
  )
}

function RequestMeta({
  icon,
  value,
  className,
}: {
  icon: React.ReactNode
  value: string
  className?: string
}) {
  return (
    <div className={cn('flex h-8 min-w-0 max-w-full items-center gap-2 rounded-full bg-muted/[0.22] px-3 text-xs font-medium text-muted-foreground', className)}>
      <span className="shrink-0 text-muted-foreground/90">{icon}</span>
      <span className="truncate leading-none">{value}</span>
    </div>
  )
}

function SeriesChip({
  selected,
  label,
  sampleModel,
  onClick,
  isAll = false,
}: {
  selected: boolean
  label: string
  sampleModel: string
  onClick: () => void
  isAll?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group flex min-w-[108px] snap-start flex-col items-center justify-center gap-2 rounded-[22px] border bg-card px-4 py-4 text-center transition-all',
        selected
          ? 'border-primary bg-primary/[0.05] shadow-[0_0_0_1px_rgba(37,99,235,0.08)]'
          : 'border-border/70 hover:border-primary/25 hover:bg-muted/20'
      )}
    >
      <span
        className={cn(
          'flex size-11 items-center justify-center rounded-2xl border bg-background',
          selected ? 'border-primary/20 bg-primary/[0.06]' : 'border-border/60'
        )}
      >
        {isAll ? <LayoutGrid size={20} className={selected ? 'text-primary' : 'text-muted-foreground'} /> : <ModelAvatar name={sampleModel} size={28} />}
      </span>
      <div className="text-sm font-medium text-foreground">{label}</div>
    </button>
  )
}

function AttemptChain({ detail, locale }: { detail: RequestLogDetail; locale: 'zh-CN' | 'en-US' }) {
  const attempts = detail.attempts.length
      ? detail.attempts
      : [{
        channel_id: detail.channel_id || 'n/a',
        channel_name: detail.channel_name || detail.channel_id || 'n/a',
        model_name: detail.upstream_model_name || detail.resolved_group_name || detail.requested_group_name || null,
        status_code: detail.status_code,
        success: detail.success,
        duration_ms: detail.latency_ms,
        error_message: detail.error_message || null,
      }]

  return (
    <ItemGroup className="gap-2.5">
      {attempts.map((attempt, index) => {
        const errorDisplay = formatErrorDisplay(attempt.error_message)
        return (
          <Item key={`${attempt.channel_id}-${index}`} variant="outline" className="items-start gap-3 px-4 py-3.5">
            <ItemMedia variant="icon" className="flex size-7 rounded-full bg-muted text-xs font-semibold text-muted-foreground">
              {index + 1}
            </ItemMedia>
            <ItemContent className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <ItemTitle className="max-w-[220px] truncate font-medium">{attempt.channel_name}</ItemTitle>
                {attempt.model_name ? <ItemDescription className="max-w-[220px] truncate">{attempt.model_name}</ItemDescription> : null}
                <StatusBadge success={attempt.success} locale={locale} errorMessage={errorDisplay} />
              </div>
              {errorDisplay ? <div className="mt-2 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive whitespace-pre-wrap break-words">{errorDisplay}</div> : null}
            </ItemContent>
            <ItemActions className="ml-auto shrink-0 text-xs text-muted-foreground">
              <StatusCodeBadge statusCode={attempt.status_code} />
              <span>{formatMs(attempt.duration_ms)}</span>
            </ItemActions>
          </Item>
        )
      })}
    </ItemGroup>
  )
}

function RequestCard({
  item,
  locale,
  timeZone,
  onPrefetchDetail,
  onOpenDetail,
  onOpenAttempts,
}: {
  item: RequestLogItem
  locale: 'zh-CN' | 'en-US'
  timeZone?: string
  onPrefetchDetail: () => void
  onOpenDetail: () => void
  onOpenAttempts: () => void
}) {
  const hoverPrefetchTimerRef = useRef<number | null>(null)
  const primaryModelName = getResolvedGroupName(item)
  const modelChain = getModelChain(item)
  const secondaryModelName = getSecondaryModelName(item)
  const attemptCount = Number.isFinite(item.attempt_count) ? item.attempt_count : 0
  const showAttemptButton = attemptCount > 1
  const errorDisplay = formatErrorDisplay(item.error_message)

  useEffect(() => {
    return () => {
      if (hoverPrefetchTimerRef.current !== null) {
        window.clearTimeout(hoverPrefetchTimerRef.current)
      }
    }
  }, [])

  function cancelHoverPrefetch() {
    if (hoverPrefetchTimerRef.current !== null) {
      window.clearTimeout(hoverPrefetchTimerRef.current)
      hoverPrefetchTimerRef.current = null
    }
  }

  function scheduleHoverPrefetch() {
    cancelHoverPrefetch()
    hoverPrefetchTimerRef.current = window.setTimeout(() => {
      hoverPrefetchTimerRef.current = null
      onPrefetchDetail()
    }, DETAIL_PREFETCH_HOVER_DELAY_MS)
  }

  return (
    <Item
      variant="outline"
      className={cn(
        'rounded-2xl px-4 py-4 transition-colors hover:bg-muted/20',
        item.success ? '' : 'border-destructive/25 bg-destructive/[0.015]'
      )}
    >
      <div
        role="button"
        tabIndex={0}
        onMouseEnter={scheduleHoverPrefetch}
        onMouseLeave={cancelHoverPrefetch}
        onFocus={() => {
          cancelHoverPrefetch()
          onPrefetchDetail()
        }}
        onBlur={cancelHoverPrefetch}
        onClick={onOpenDetail}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onOpenDetail()
          }
        }}
        className="grid w-full min-w-0 cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3.5 gap-y-3 outline-none focus-visible:ring-2 focus-visible:ring-ring/50 sm:grid-cols-[56px_minmax(0,1fr)_auto]"
      >
        <ItemMedia variant="icon" className="hidden size-12 self-start rounded-2xl border bg-muted/40 sm:flex">
          <ModelAvatar name={primaryModelName} size={28} />
        </ItemMedia>

        <ItemContent className="min-w-0 gap-3">
          <div className="grid gap-2.5">
            <div className="min-w-0">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <ItemTitle className="min-w-0 max-w-full truncate text-[15px] leading-6">{modelChain}</ItemTitle>
                <ProtocolBadge protocol={item.protocol} />
                <StatusCodeBadge statusCode={item.status_code} />
                <StatusBadge success={item.success} locale={locale} errorMessage={errorDisplay} />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <RequestMeta icon={<Clock3 size={13} />} value={formatLogDateTime(item.created_at, locale, timeZone)} className="pl-0" />
              <RequestMeta icon={<Waypoints size={13} />} value={item.channel_name || item.channel_id || 'n/a'} />
              {item.gateway_key_id ? <RequestMeta icon={<KeyRound size={13} />} value={formatGatewayKeyLabel(item, locale)} /> : null}
              {secondaryModelName ? <RequestMeta icon={<ServerCog size={13} />} value={secondaryModelName} /> : null}
            </div>
          </div>
        </ItemContent>

        {showAttemptButton ? (
          <div className="self-start">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={(event) => {
                event.stopPropagation()
                onOpenAttempts()
              }}
            >
              <Waypoints data-icon="inline-start" />
              {locale === 'zh-CN' ? `链路 ${attemptCount}` : `Attempts ${attemptCount}`}
            </Button>
          </div>
        ) : <div />}

        <div className="col-span-full grid w-full grid-cols-[repeat(auto-fit,minmax(126px,1fr))] gap-2">
          <RequestMetric icon={<Zap size={14} />} label={locale === 'zh-CN' ? '首字延迟' : 'First token'} value={formatMs(item.first_token_latency_ms)} />
          <RequestMetric icon={<ServerCog size={14} />} label={locale === 'zh-CN' ? '总耗时' : 'Total'} value={formatMs(item.latency_ms)} />
          <RequestMetric icon={<ArrowDownToLine size={14} />} label={locale === 'zh-CN' ? '输入' : 'Input'} value={formatCount(item.input_tokens)} />
          <RequestMetric icon={<ArrowUpFromLine size={14} />} label={locale === 'zh-CN' ? '输出' : 'Output'} value={formatCount(item.output_tokens)} />
          <RequestMetric icon={<Database size={14} />} label={locale === 'zh-CN' ? '缓存读取' : 'Cache Read'} value={formatCount(item.cache_read_input_tokens)} />
          <RequestMetric icon={<Upload size={14} />} label={locale === 'zh-CN' ? '缓存写入' : 'Cache Write'} value={formatCount(item.cache_write_input_tokens)} />
          <RequestMetric
            icon={<DollarSign size={14} />}
            label={locale === 'zh-CN' ? '费用' : 'Cost'}
            value={formatMoney(item.total_cost_usd)}
            valueClassName="whitespace-nowrap break-normal text-[12px]"
          />
        </div>
      </div>
    </Item>
  )
}

export function RequestsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const timeZone = useAppTimeZone()
  const [detailId, setDetailId] = useState<number | null>(null)
  const [attemptDetailId, setAttemptDetailId] = useState<number | null>(null)
  const [showBackToTop, setShowBackToTop] = useState(false)
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)
  const [page, setPage] = useState(0)
  const [selectedSeries, setSelectedSeries] = useState<SelectedSeries>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [protocolFilter, setProtocolFilter] = useState<'all' | ProtocolKind>('all')
  const [channelFilter, setChannelFilter] = useState('all')
  const [selectedGatewayKeyId, setSelectedGatewayKeyId] = useState('all')
  const [sortMode, setSortMode] = useState<SortMode>('latest')
  const [keyword, setKeyword] = useState('')
  const [clearingLogs, setClearingLogs] = useState(false)
  const deferredKeyword = useDeferredValue(keyword.trim().toLowerCase())
  const effectiveGatewayKeyId = selectedGatewayKeyId === 'all' ? null : selectedGatewayKeyId

  const requestLogsQuery = useMemo(() => {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    })
    if (effectiveGatewayKeyId) {
      params.set('gateway_key_id', effectiveGatewayKeyId)
    }
    return `/admin/request-logs/page?${params.toString()}`
  }, [effectiveGatewayKeyId, page])

  const overviewModelsQuery = useMemo(() => {
    const params = new URLSearchParams({
      days: '0',
    })
    if (effectiveGatewayKeyId) {
      params.set('gateway_key_id', effectiveGatewayKeyId)
    }
    return `/admin/overview-models?${params.toString()}`
  }, [effectiveGatewayKeyId])

  const {
    data,
    isLoading,
    isFetching,
    refetch: refetchRequestLogs,
  } = useQuery({
    queryKey: ['request-logs', page, effectiveGatewayKeyId],
    queryFn: () => apiRequest<RequestLogPage>(requestLogsQuery),
    placeholderData: keepPreviousData,
    refetchInterval: page === 0 ? 5000 : false,
  })

  const { data: allModels, refetch: refetchAllModels } = useQuery({
    queryKey: ['overview-models', 'requests-screen', effectiveGatewayKeyId],
    queryFn: () => apiRequest<OverviewModelAnalytics>(overviewModelsQuery),
    staleTime: 5 * 60_000,
  })

  const { data: gatewayApiKeys } = useQuery({
    queryKey: ['gateway-api-keys', 'requests-screen'],
    queryFn: () => apiRequest<GatewayApiKey[]>('/admin/gateway-api-keys'),
    staleTime: 60_000,
  })

  const { data: detail, isLoading: detailLoading, refetch: refetchDetail } = useQuery({
    queryKey: ['request-log-detail', detailId],
    queryFn: () => apiRequest<RequestLogDetail>(`/admin/request-logs/${detailId}`),
    enabled: detailId !== null,
    staleTime: 60_000,
  })

  const { data: attemptDetail, isLoading: attemptDetailLoading, refetch: refetchAttemptDetail } = useQuery({
    queryKey: ['request-log-attempt-detail', attemptDetailId],
    queryFn: () => apiRequest<RequestLogDetail>(`/admin/request-logs/${attemptDetailId}`),
    enabled: attemptDetailId !== null,
    staleTime: 60_000,
  })

  const filteredBaseData = useMemo(() => {
    return (data?.items ?? []).filter((item) => {
      if (statusFilter === 'success' && !item.success) return false
      if (statusFilter === 'failed' && item.success) return false
      if (protocolFilter !== 'all' && item.protocol !== protocolFilter) return false
      if (channelFilter !== 'all' && (item.channel_name || item.channel_id || 'n/a') !== channelFilter) return false
      if (deferredKeyword) {
        const haystack = [
          getModelChain(item),
          item.requested_group_name,
          item.resolved_group_name,
          item.upstream_model_name,
          item.channel_name,
          item.channel_id,
          item.gateway_key_id,
          item.gateway_key_remark,
          item.error_message,
          item.protocol,
          String(item.status_code),
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        if (!haystack.includes(deferredKeyword)) return false
      }
      return true
    })
  }, [channelFilter, data?.items, deferredKeyword, protocolFilter, statusFilter])

  const seriesOptions = useMemo(() => {
    const availableKeys = new Set<ModelSeriesKey>()
    for (const model of allModels?.available_models ?? []) {
      availableKeys.add(getSeriesPreset(model).key)
    }
    if (!availableKeys.size) {
      for (const item of filteredBaseData) {
        availableKeys.add(getSeriesKey(item))
      }
    }

    const available = MODEL_SERIES_PRESETS.filter((preset) => availableKeys.has(preset.key))

    return [{
      key: 'all' as const,
      zh: '全部',
      en: 'All',
      sampleModel: 'all',
    }, ...available]
  }, [allModels?.available_models, filteredBaseData])

  const effectiveSelectedSeries = seriesOptions.some((item) => item.key === selectedSeries)
    ? selectedSeries
    : 'all'

  const visibleData = useMemo(() => {
    const list = filteredBaseData
      .filter((item) => effectiveSelectedSeries === 'all' || getSeriesKey(item) === effectiveSelectedSeries)
      .slice()

    list.sort((a, b) => {
      if (sortMode === 'cost') return b.total_cost_usd - a.total_cost_usd
      if (sortMode === 'latency') return b.latency_ms - a.latency_ms
      if (sortMode === 'tokens') return b.total_tokens - a.total_tokens
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

    return list
  }, [effectiveSelectedSeries, filteredBaseData, sortMode])

  const channelOptions = useMemo(() => {
    return [...new Set((data?.items ?? []).map((item) => item.channel_name || item.channel_id || 'n/a'))].sort((a, b) => a.localeCompare(b))
  }, [data?.items])

  const gatewayKeyOptions = useMemo(() => {
    const items = (gatewayApiKeys ?? []).map((item) => ({
      id: item.id,
      label: formatGatewayKeyOptionLabel(item),
    }))
    if (effectiveGatewayKeyId && !items.some((item) => item.id === effectiveGatewayKeyId)) {
      items.unshift({
        id: effectiveGatewayKeyId,
        label: shortenGatewayKeyId(effectiveGatewayKeyId),
      })
    }
    return items
  }, [effectiveGatewayKeyId, gatewayApiKeys])

  const total = data?.total ?? 0
  const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1)
  const hasNextPage = page < totalPages - 1
  const paginationItems = buildPaginationItems(page + 1, totalPages)
  const activeFilterCount = [
    effectiveSelectedSeries !== 'all',
    statusFilter !== 'all',
    protocolFilter !== 'all',
    channelFilter !== 'all',
    effectiveGatewayKeyId !== null,
    !!keyword.trim(),
  ].filter(Boolean).length

  useEffect(() => {
    function handleScroll() {
      setShowBackToTop(window.scrollY > 320)
    }

    handleScroll()
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  function handleSeriesChange(value: SelectedSeries) {
    setSelectedSeries(value)
    setPage(0)
  }

  function handleStatusChange(value: StatusFilter) {
    setStatusFilter(value)
    setPage(0)
  }

  function handleProtocolChange(value: 'all' | ProtocolKind) {
    setProtocolFilter(value)
    setPage(0)
  }

  function handleChannelChange(value: string) {
    setChannelFilter(value)
    setPage(0)
  }

  function handleGatewayKeyChange(value: string) {
    setSelectedGatewayKeyId(value)
    setPage(0)
  }

  function handleKeywordChange(value: string) {
    setKeyword(value)
    setPage(0)
  }

  function resetFilters() {
    setSelectedSeries('all')
    setStatusFilter('all')
    setProtocolFilter('all')
    setChannelFilter('all')
    setSelectedGatewayKeyId('all')
    setSortMode('latest')
    setKeyword('')
    setPage(0)
  }

  function prefetchRequestDetail(id: number) {
    const queryKey = ['request-log-detail', id] as const
    const queryState = queryClient.getQueryState<RequestLogDetail>(queryKey)

    if (queryState?.fetchStatus === 'fetching') {
      return
    }

    if (queryClient.getQueryData<RequestLogDetail>(queryKey) !== undefined) {
      return
    }

    void queryClient.prefetchQuery({
      queryKey,
      queryFn: () => apiRequest<RequestLogDetail>(`/admin/request-logs/${id}`),
      staleTime: 60_000,
    })
  }

  async function refreshLogs() {
    await Promise.all([
      refetchRequestLogs(),
      refetchAllModels(),
      detailId !== null ? refetchDetail() : Promise.resolve(),
      attemptDetailId !== null ? refetchAttemptDetail() : Promise.resolve(),
    ])
  }

  async function clearRequestLogs() {
    const confirmed = window.confirm(locale === 'zh-CN' ? '确认删除全部请求日志？' : 'Delete all request logs?')
    if (!confirmed) {
      return
    }
    setClearingLogs(true)
    try {
      await apiRequest<void>('/admin/request-logs', { method: 'DELETE' })
      setPage(0)
      setDetailId(null)
      setAttemptDetailId(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['request-logs'] }),
        queryClient.invalidateQueries({ queryKey: ['overview'] }),
        queryClient.invalidateQueries({ queryKey: ['overview-dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['overview-summary'] }),
        queryClient.invalidateQueries({ queryKey: ['overview-daily'] }),
        queryClient.invalidateQueries({ queryKey: ['overview-models'] }),
        queryClient.invalidateQueries({ queryKey: ['overview-logs'] }),
        queryClient.invalidateQueries({ queryKey: ['gateway-api-keys'] }),
      ])
      toast.success(locale === 'zh-CN' ? '请求日志已清空' : 'Request logs cleared')
    } catch (requestError) {
      toast.error(
        requestError instanceof ApiError
          ? requestError.message
          : (locale === 'zh-CN' ? '清空请求日志失败' : 'Failed to clear request logs')
      )
    } finally {
      setClearingLogs(false)
    }
  }

  return (
    <TooltipProvider>
      <section className="flex flex-col gap-4 md:gap-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{locale === 'zh-CN' ? '请求日志' : 'Requests'}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2 self-start lg:self-auto">
          <Button type="button" variant="outline" onClick={() => void refreshLogs()} disabled={isFetching}>
            <RefreshCcw data-icon="inline-start" className={cn(isFetching && 'animate-spin')} />
            {locale === 'zh-CN' ? '刷新' : 'Refresh'}
          </Button>
          <Button type="button" variant="outline" onClick={resetFilters} disabled={!activeFilterCount && sortMode === 'latest'}>
            <RotateCcw data-icon="inline-start" />
            {locale === 'zh-CN' ? '重置' : 'Reset'}
          </Button>
        </div>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,4fr)_320px]">
        <div className="order-2 grid gap-4 xl:order-1">
          <div className="rounded-2xl border bg-card px-4 py-3 sm:px-5 sm:py-4">
            <div className="flex items-center justify-between gap-3 sm:mb-3">
              <div>
                <div className="text-base font-semibold text-foreground">{locale === 'zh-CN' ? '选择模型系列' : 'Choose model series'}</div>
              </div>
            </div>

            <NativeSelect
              className="mt-3 w-full sm:hidden"
              value={effectiveSelectedSeries}
              onChange={(event) => handleSeriesChange(event.target.value as SelectedSeries)}
            >
              {seriesOptions.map((option) => (
                <NativeSelectOption key={option.key} value={option.key}>
                  {locale === 'zh-CN' ? option.zh : option.en}
                </NativeSelectOption>
              ))}
            </NativeSelect>

            <div className="hidden snap-x gap-3 overflow-x-auto pb-1 sm:flex">
              {seriesOptions.map((option) => (
                <SeriesChip
                  key={option.key}
                  selected={effectiveSelectedSeries === option.key}
                  label={locale === 'zh-CN' ? option.zh : option.en}
                  sampleModel={option.sampleModel}
                  isAll={option.key === 'all'}
                  onClick={() => handleSeriesChange(option.key)}
                />
              ))}
            </div>
          </div>

          <div className="rounded-2xl border bg-card p-3 sm:p-4">
            {isLoading ? <p className="px-2 py-6 text-sm text-muted-foreground">{locale === 'zh-CN' ? '正在加载请求日志...' : 'Loading request logs...'}</p> : null}

            {!isLoading && visibleData.length === 0 ? (
              <div className="rounded-xl border border-dashed bg-background px-6 py-14 text-center text-sm text-muted-foreground">
                {activeFilterCount
                  ? (locale === 'zh-CN' ? '当前筛选条件下没有请求日志。' : 'No request logs match the current filters.')
                  : (locale === 'zh-CN' ? '暂无请求日志。' : 'No request logs yet.')}
              </div>
            ) : null}

            {visibleData.length ? (
              <ItemGroup className="gap-3">
                {visibleData.map((item) => (
                  <RequestCard
                    key={item.id}
                    item={item}
                    locale={locale}
                    timeZone={timeZone}
                    onPrefetchDetail={() => prefetchRequestDetail(item.id)}
                    onOpenDetail={() => setDetailId(item.id)}
                    onOpenAttempts={() => setAttemptDetailId(item.id)}
                  />
                ))}
              </ItemGroup>
            ) : null}
          </div>
        </div>

        <aside className="order-1 xl:order-2">
          <div className="rounded-2xl border bg-card p-4 xl:sticky xl:top-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-9 items-center justify-center rounded-xl bg-primary/[0.08] text-primary">
                  <Filter size={16} />
                </span>
                <div>
                  <div className="text-sm font-semibold text-foreground">{locale === 'zh-CN' ? '筛选' : 'Filters'}</div>
                  <div className="text-xs text-muted-foreground">
                    {locale === 'zh-CN' ? `已启用 ${activeFilterCount} 项` : `${activeFilterCount} active`}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <Button type="button" variant="ghost" size="sm" onClick={resetFilters} disabled={!activeFilterCount && sortMode === 'latest'}>
                  {locale === 'zh-CN' ? '清空' : 'Clear'}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="xl:hidden"
                  onClick={() => setMobileFiltersOpen((current) => !current)}
                  aria-expanded={mobileFiltersOpen}
                  aria-label={locale === 'zh-CN' ? '展开筛选' : 'Toggle filters'}
                >
                  <ChevronDown className={cn('transition-transform', mobileFiltersOpen && 'rotate-180')} />
                </Button>
              </div>
            </div>

            <div className={cn('mt-4', !mobileFiltersOpen && 'hidden xl:block')}>
              <FieldSet className="gap-4">
                <FieldLegend>{locale === 'zh-CN' ? '筛选条件' : 'Refine results'}</FieldLegend>
                <FieldGroup className="gap-4">
                  <Field>
                    <FieldLabel>{locale === 'zh-CN' ? '关键词' : 'Keyword'}</FieldLabel>
                    <ToolbarSearchInput
                      value={keyword}
                      onChange={handleKeywordChange}
                      onClear={() => handleKeywordChange('')}
                      placeholder={locale === 'zh-CN' ? '模型 / 渠道 / API Key / 错误 / 状态码' : 'Model / channel / API key / error / status'}
                      className="max-w-none"
                    />
                  </Field>

                  <Field>
                    <FieldLabel>{locale === 'zh-CN' ? '状态' : 'Status'}</FieldLabel>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { key: 'all' as const, label: locale === 'zh-CN' ? '全部' : 'All' },
                        { key: 'success' as const, label: locale === 'zh-CN' ? '成功' : 'Success' },
                        { key: 'failed' as const, label: locale === 'zh-CN' ? '失败' : 'Failed' },
                      ].map((option) => (
                        <Button
                          key={option.key}
                          type="button"
                          variant={statusFilter === option.key ? 'default' : 'outline'}
                          size="sm"
                          className="min-w-0 truncate px-1.5"
                          onClick={() => handleStatusChange(option.key)}
                        >
                          {option.label}
                        </Button>
                      ))}
                    </div>
                  </Field>

                  <Field>
                    <FieldLabel htmlFor="request-log-protocol">{locale === 'zh-CN' ? '协议' : 'Protocol'}</FieldLabel>
                    <NativeSelect id="request-log-protocol" className="w-full" value={protocolFilter} onChange={(event) => handleProtocolChange(event.target.value as 'all' | ProtocolKind)}>
                      <NativeSelectOption value="all">{locale === 'zh-CN' ? '全部协议' : 'All protocols'}</NativeSelectOption>
                      <NativeSelectOption value="openai_chat">OpenAI Chat</NativeSelectOption>
                      <NativeSelectOption value="openai_responses">OpenAI Responses</NativeSelectOption>
                      <NativeSelectOption value="anthropic">Anthropic</NativeSelectOption>
                      <NativeSelectOption value="gemini">Gemini</NativeSelectOption>
                    </NativeSelect>
                  </Field>

                  <Field>
                    <FieldLabel htmlFor="request-log-channel">{locale === 'zh-CN' ? '渠道' : 'Channel'}</FieldLabel>
                    <NativeSelect id="request-log-channel" className="w-full" value={channelFilter} onChange={(event) => handleChannelChange(event.target.value)}>
                      <NativeSelectOption value="all">{locale === 'zh-CN' ? '全部渠道' : 'All channels'}</NativeSelectOption>
                      {channelOptions.map((channel) => <NativeSelectOption key={channel} value={channel}>{channel}</NativeSelectOption>)}
                    </NativeSelect>
                  </Field>

                  <Field>
                    <FieldLabel htmlFor="request-log-gateway-key">API Key</FieldLabel>
                    <NativeSelect id="request-log-gateway-key" className="w-full" value={selectedGatewayKeyId} onChange={(event) => handleGatewayKeyChange(event.target.value)}>
                      <NativeSelectOption value="all">{locale === 'zh-CN' ? '全部 API Key' : 'All API keys'}</NativeSelectOption>
                      {gatewayKeyOptions.map((item) => <NativeSelectOption key={item.id} value={item.id}>{item.label}</NativeSelectOption>)}
                    </NativeSelect>
                  </Field>

                  <Field>
                    <FieldLabel htmlFor="request-log-sort">{locale === 'zh-CN' ? '排序' : 'Sort by'}</FieldLabel>
                    <NativeSelect id="request-log-sort" className="w-full" value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)}>
                      <NativeSelectOption value="latest">{locale === 'zh-CN' ? '最新优先' : 'Latest first'}</NativeSelectOption>
                      <NativeSelectOption value="cost">{locale === 'zh-CN' ? '费用优先' : 'Highest cost'}</NativeSelectOption>
                      <NativeSelectOption value="latency">{locale === 'zh-CN' ? '耗时优先' : 'Longest latency'}</NativeSelectOption>
                      <NativeSelectOption value="tokens">{locale === 'zh-CN' ? 'Token 优先' : 'Most tokens'}</NativeSelectOption>
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
                    ? (locale === 'zh-CN' ? '清空中...' : 'Clearing...')
                    : (locale === 'zh-CN' ? '清空请求日志' : 'Clear request logs')}
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
                text={locale === 'zh-CN' ? '上一页' : 'Prev'}
                onClick={(event) => {
                  event.preventDefault()
                  if (page === 0) return
                  setPage((current) => Math.max(current - 1, 0))
                }}
                className={cn(page === 0 && 'pointer-events-none opacity-50')}
              />
            </PaginationItem>
            {paginationItems.map((item, index) => (
              <PaginationItem key={`${item}-${index}`}>
                {item === 'ellipsis' ? (
                  <PaginationEllipsis />
                ) : (
                  <PaginationLink
                    href="#requests-pagination"
                    size="default"
                    isActive={item === page + 1}
                    onClick={(event) => {
                      event.preventDefault()
                      if (item === page + 1) return
                      setPage(item - 1)
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
                text={locale === 'zh-CN' ? '下一页' : 'Next'}
                onClick={(event) => {
                  event.preventDefault()
                  if (!hasNextPage) return
                  setPage((current) => current + 1)
                }}
                className={cn(!hasNextPage && 'pointer-events-none opacity-50')}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      ) : null}

      <Dialog open={detailId !== null} onOpenChange={(open) => { if (!open) setDetailId(null) }}>
        <AppDialogContent className="max-w-6xl" title={locale === 'zh-CN' ? '日志详情' : 'Log detail'}>
          {detailLoading || !detail ? (
            <div className="rounded-md border bg-background px-5 py-8 text-sm text-muted-foreground">
              {locale === 'zh-CN' ? '正在加载详情...' : 'Loading detail...'}
            </div>
          ) : (
            <div className="grid gap-3">
              <div className="grid min-h-[60dvh] overflow-hidden sm:min-h-[560px] xl:grid-cols-2">
                <JsonViewer
                  key={`request-${detail.id}`}
                  title={locale === 'zh-CN' ? '请求内容' : 'Request'}
                  content={detail.request_content}
                  emptyText={locale === 'zh-CN' ? '无输入内容' : 'No request content'}
                  locale={locale}
                />

                <JsonViewer
                  key={`response-${detail.id}`}
                  className="border-t xl:border-t-0 xl:border-l"
                  title={locale === 'zh-CN' ? '响应内容' : 'Response'}
                  content={detail.response_content}
                  emptyText={locale === 'zh-CN' ? '无输出内容' : 'No response content'}
                  locale={locale}
                />
              </div>
            </div>
          )}
        </AppDialogContent>
      </Dialog>

      <Dialog open={attemptDetailId !== null} onOpenChange={(open) => { if (!open) setAttemptDetailId(null) }}>
        <AppDialogContent className="max-w-4xl" title={locale === 'zh-CN' ? '尝试链路' : 'Attempts'}>
          {attemptDetailLoading || !attemptDetail ? (
            <div className="rounded-md border bg-background px-5 py-8 text-sm text-muted-foreground">
              {locale === 'zh-CN' ? '正在加载尝试链路...' : 'Loading attempts...'}
            </div>
          ) : (
            <div className="grid gap-4">
              {formatErrorDisplay(attemptDetail.error_message) ? (
                <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-4 text-sm text-destructive">
                  <div className="flex items-start gap-3">
                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                    <span className="whitespace-pre-wrap break-words">{formatErrorDisplay(attemptDetail.error_message)}</span>
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
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            >
              <ArrowUp />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="left">
            {locale === 'zh-CN' ? '返回顶部' : 'Back to top'}
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
  )
}
