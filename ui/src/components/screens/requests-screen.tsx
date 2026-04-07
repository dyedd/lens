"use client"

import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
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
} from 'lucide-react'
import { RequestLogDetail, RequestLogItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/cn'
import { getModelGroupAvatar } from '@/lib/model-icons'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'

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

function formatDate(value: string, locale: 'zh-CN' | 'en-US') {
  return new Date(value).toLocaleString(locale === 'zh-CN' ? 'zh-CN' : 'en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function JsonPanel({ content, emptyText }: { content?: string | null; emptyText: string }) {
  if (!content) {
    return <div className="px-4 py-4 text-xs text-[var(--muted)]">{emptyText}</div>
  }

  let formatted = content
  try {
    formatted = JSON.stringify(JSON.parse(content), null, 2)
  } catch {
    formatted = content
  }

  return <pre className="max-h-[440px] overflow-auto px-4 py-4 text-xs leading-6 text-[var(--text)]">{formatted}</pre>
}

function MetricPill({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="inline-flex min-h-8 items-center gap-2 text-sm text-[var(--muted)]">
      <span className="inline-flex h-5 w-5 items-center justify-center">{icon}</span>
      <span>{label} {value}</span>
    </div>
  )
}

function DetailStat({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-[22px] border border-[var(--line)] bg-[var(--panel)] px-4 py-4">
      <div className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)]">{label}</div>
      <div className={cn('mt-3 text-lg font-semibold', accent ? 'text-[var(--accent)]' : 'text-[var(--text)]')}>{value}</div>
    </div>
  )
}

function StatusBadge({ success, locale }: { success: boolean; locale: 'zh-CN' | 'en-US' }) {
  return (
    <span
      className={cn(
        'rounded-full px-3 py-1.5 text-xs font-medium',
        success
          ? 'bg-[rgba(37,99,235,0.10)] text-[var(--accent)]'
          : 'bg-[rgba(217,111,93,0.12)] text-[var(--danger)]'
      )}
    >
      {success ? (locale === 'zh-CN' ? '成功' : 'Success') : (locale === 'zh-CN' ? '失败' : 'Failed')}
    </span>
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
    <span className="inline-flex items-center rounded-full bg-[rgba(30,160,140,0.14)] px-3 py-1 text-xs font-medium text-[rgb(19,146,126)]">
      {labelMap[protocol] ?? protocol}
    </span>
  )
}

function AttemptChain({ detail, locale }: { detail: RequestLogDetail; locale: 'zh-CN' | 'en-US' }) {
  const attempts = detail.attempts.length
    ? detail.attempts
    : [{
        channel_id: detail.channel_id || 'n/a',
        channel_name: detail.channel_name || detail.channel_id || 'n/a',
        model_name: detail.resolved_model || detail.requested_model || null,
        status_code: detail.status_code,
        success: detail.success,
        duration_ms: detail.latency_ms,
        error_message: detail.error_message || null,
      }]

  return (
    <div className="grid gap-3">
      {attempts.map((attempt, index) => (
        <div key={`${attempt.channel_id}-${index}`} className="rounded-[22px] border border-[var(--line)] bg-[var(--panel)] px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full bg-[var(--panel-strong)] px-2 text-xs font-semibold text-[var(--muted)]">{index + 1}</span>
              <span className="font-medium text-[var(--text)]">{attempt.channel_name}</span>
              {attempt.model_name ? <span className="text-[var(--muted)]">{attempt.model_name}</span> : null}
              <StatusBadge success={attempt.success} locale={locale} />
            </div>
            <div className="flex items-center gap-3 text-xs text-[var(--muted)]">
              <span>{attempt.status_code ?? '-'}</span>
              <span>{formatMs(attempt.duration_ms)}</span>
            </div>
          </div>
          {attempt.error_message ? <div className="mt-3 rounded-2xl bg-[rgba(217,111,93,0.08)] px-3 py-2 text-xs text-[var(--danger)]">{attempt.error_message}</div> : null}
        </div>
      ))}
    </div>
  )
}

function RequestCard({
  item,
  locale,
  onToggle,
}: {
  item: RequestLogItem
  locale: 'zh-CN' | 'en-US'
  onToggle: () => void
}) {
  const Avatar = getModelGroupAvatar(item.requested_model || item.resolved_model || '')

  return (
    <article
      className={cn(
        'overflow-hidden rounded-[30px] border bg-[var(--panel-strong)] shadow-[var(--shadow-sm)] transition-all duration-200 border-[var(--line)] hover:border-[color:color-mix(in_oklab,var(--accent)_18%,var(--line))] hover:bg-[var(--panel-soft)]',
        item.success ? '' : 'border-[rgba(217,111,93,0.24)]'
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left"
      >
        <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 px-5 py-5 lg:px-6">
          <div className="row-span-2 flex h-12 w-12 shrink-0 items-center justify-center self-start rounded-2xl border border-[var(--line)] bg-[var(--panel)] shadow-[inset_0_1px_0_rgba(255,255,255,0.45)]">
              <Avatar size={28} />
          </div>

          <div className="min-w-0 self-center">
            <div className="flex flex-wrap items-center gap-2 text-[15px] leading-none">
              <span className="font-semibold text-[var(--text)]">{item.requested_model || item.resolved_model || 'n/a'}</span>
              <ProtocolBadge protocol={item.protocol} />
              <StatusBadge success={item.success} locale={locale} />
              {item.resolved_model && item.resolved_model !== item.requested_model ? <span className="truncate text-[var(--muted)]">{item.resolved_model}</span> : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 self-center pt-0.5 lg:flex-nowrap lg:gap-x-5 lg:gap-y-0">
            <MetricPill icon={<Clock3 size={14} className="text-[rgb(26,174,155)]" />} label="" value={formatDate(item.created_at, locale)} />
            <MetricPill icon={<Waypoints size={14} className="text-[rgb(238,137,54)]" />} label="" value={item.channel_name || item.channel_id || 'n/a'} />
            <MetricPill icon={<Zap size={14} className="text-[rgb(238,137,54)]" />} label={locale === 'zh-CN' ? '首字' : 'First'} value={formatMs(item.first_token_latency_ms)} />
            <MetricPill icon={<ServerCog size={14} className="text-[rgb(70,116,255)]" />} label={locale === 'zh-CN' ? '总耗时' : 'Total'} value={formatMs(item.latency_ms)} />
            <MetricPill icon={<ArrowDownToLine size={14} className="text-[rgb(24,180,103)]" />} label={locale === 'zh-CN' ? '输入' : 'Input'} value={formatCount(item.input_tokens)} />
            <MetricPill icon={<ArrowUpFromLine size={14} className="text-[rgb(164,73,255)]" />} label={locale === 'zh-CN' ? '输出' : 'Output'} value={formatCount(item.output_tokens)} />
            <MetricPill icon={<DollarSign size={14} className="text-[rgb(0,162,112)]" />} label={locale === 'zh-CN' ? '费用' : 'Cost'} value={formatMoney(item.total_cost_usd)} />
          </div>
        </div>
      </button>
    </article>
  )
}

export function RequestsScreen() {
  const { locale } = useI18n()
  const [showFailedOnly, setShowFailedOnly] = useState(false)
  const [detailId, setDetailId] = useState<number | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['request-logs'],
    queryFn: () => apiRequest<RequestLogItem[]>('/request-logs'),
    refetchInterval: 5000,
  })

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ['request-log-detail', detailId],
    queryFn: () => apiRequest<RequestLogDetail>(`/request-logs/${detailId}`),
    enabled: detailId !== null,
  })

  const visibleData = useMemo(() => {
    const list = data ?? []
    return showFailedOnly ? list.filter((item) => !item.success) : list
  }, [data, showFailedOnly])

  const failedCount = useMemo(() => (data ?? []).filter((item) => !item.success).length, [data])

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-end gap-2">
        <button
          className={showFailedOnly
            ? 'inline-flex h-9 items-center gap-2 rounded-xl bg-[var(--accent)] px-3 text-sm text-white'
            : 'inline-flex h-9 items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 text-sm text-[var(--text)]'}
          type="button"
          onClick={() => setShowFailedOnly((current) => !current)}
        >
          <Filter size={15} />
          {locale === 'zh-CN' ? `仅看失败 ${failedCount ? `(${failedCount})` : ''}` : `Failed only${failedCount ? ` (${failedCount})` : ''}`}
        </button>
      </div>

      <div className="grid gap-4">
        {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载请求日志...' : 'Loading request logs...'}</p> : null}

        {!isLoading && visibleData.length === 0 ? (
          <div className="rounded-[28px] border border-dashed border-[var(--line)] bg-[var(--panel-strong)] px-6 py-14 text-center text-sm text-[var(--muted)]">
            {locale === 'zh-CN' ? '暂无请求日志。' : 'No request logs yet.'}
          </div>
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

      <Dialog.Root open={detailId !== null} onOpenChange={(open) => { if (!open) setDetailId(null) }}>
        <AppDialogContent className="max-w-6xl" title={locale === 'zh-CN' ? '请求详情' : 'Request detail'}>
          {detailLoading || !detail ? (
            <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel)] px-5 py-8 text-sm text-[var(--muted)]">
              {locale === 'zh-CN' ? '正在加载详情...' : 'Loading detail...'}
            </div>
          ) : (
            <div className="grid gap-5">
              <div className="grid gap-4 lg:grid-cols-5">
                <DetailStat label={locale === 'zh-CN' ? '模型组' : 'Group'} value={detail.matched_group_name || (locale === 'zh-CN' ? '未命中' : 'No match')} />
                <DetailStat label={locale === 'zh-CN' ? '渠道' : 'Channel'} value={detail.channel_name || detail.channel_id || 'n/a'} />
                <DetailStat label={locale === 'zh-CN' ? '状态' : 'Status'} value={String(detail.status_code)} />
                <DetailStat label={locale === 'zh-CN' ? '总 Token' : 'Total token'} value={formatCount(detail.total_tokens)} />
                <DetailStat label={locale === 'zh-CN' ? '总费用' : 'Total cost'} value={formatMoney(detail.total_cost_usd)} accent />
              </div>

              {detail.error_message ? (
                <div className="rounded-[24px] border border-[rgba(217,111,93,0.16)] bg-[rgba(217,111,93,0.08)] px-4 py-4 text-sm text-[var(--danger)]">
                  <div className="flex items-start gap-3">
                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                    <span>{detail.error_message}</span>
                  </div>
                </div>
              ) : null}

              <section className="rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 lg:p-5">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '尝试链路' : 'Attempts'}</h3>
                    <p className="mt-1 text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '按实际命中与重试顺序记录' : 'Captured in routing and retry order'}</p>
                  </div>
                </div>
                <AttemptChain detail={detail} locale={locale} />
              </section>

              <div className="grid gap-5 xl:grid-cols-2">
                <section className="overflow-hidden rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)]">
                  <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-4">
                    <div>
                      <div className="text-sm font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '请求内容' : 'Request'}</div>
                      <div className="mt-1 text-xs text-[var(--muted)]">{formatCount(detail.input_tokens)} tokens</div>
                    </div>
                  </div>
                  <JsonPanel content={detail.request_content} emptyText={locale === 'zh-CN' ? '无输入内容' : 'No request content'} />
                </section>

                <section className="overflow-hidden rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)]">
                  <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-4">
                    <div>
                      <div className="text-sm font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '响应内容' : 'Response'}</div>
                      <div className="mt-1 text-xs text-[var(--muted)]">{formatCount(detail.output_tokens)} tokens</div>
                    </div>
                  </div>
                  <JsonPanel content={detail.response_content} emptyText={locale === 'zh-CN' ? '无输出内容' : 'No response content'} />
                </section>
              </div>
            </div>
          )}
        </AppDialogContent>
      </Dialog.Root>
    </section>
  )
}
