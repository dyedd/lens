"use client"

import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Clock3, Filter, RefreshCcw, Search, Zap, DollarSign, ArrowDownToLine, ArrowUpFromLine } from 'lucide-react'
import { RequestLogDetail, RequestLogItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'

function formatMs(value: number) {
  if (value < 1000) return `${value} ms`
  return `${(value / 1000).toFixed(2)} s`
}

function formatMoney(value: number) {
  return `$${value.toFixed(6)}`
}

function JsonPanel({ content, emptyText }: { content?: string | null, emptyText: string }) {
  if (!content) {
    return <div className="px-4 py-3 text-xs text-[var(--muted)]">{emptyText}</div>
  }

  let formatted = content
  try {
    formatted = JSON.stringify(JSON.parse(content), null, 2)
  } catch {
    formatted = content
  }

  return <pre className="overflow-auto px-4 py-3 text-xs leading-6 text-[var(--text)]">{formatted}</pre>
}

export function RequestsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const [showFailedOnly, setShowFailedOnly] = useState(false)
  const [detailId, setDetailId] = useState<number | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['request-logs'],
    queryFn: () => apiRequest<RequestLogItem[]>('/request-logs')
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
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] text-[var(--muted)] transition-colors hover:text-[var(--text)]" type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ['request-logs'] })}>
          <RefreshCcw size={15} />
        </button>
      </div>

      <div className="grid gap-3">
        {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载请求日志...' : 'Loading request logs...'}</p> : null}
        {visibleData.map((item) => (
          <article key={item.id} className={item.success ? 'rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]' : 'rounded-3xl border border-[rgba(217,111,93,0.22)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]'}>
            <div className="grid gap-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <strong className="font-semibold text-[var(--text)]">{item.requested_model || 'n/a'}</strong>
                  <span className="text-[var(--muted)]">→</span>
                  <span className="text-[var(--text)]">{item.resolved_model || item.channel_name || item.channel_id || 'n/a'}</span>
                  <span className="rounded-lg bg-[var(--panel)] px-2 py-1 text-[12px] text-[var(--text)]">{item.protocol}</span>
                  {item.is_stream ? <span className="rounded-lg bg-[rgba(196,142,67,0.12)] px-2 py-1 text-[11px] text-[rgb(154,101,35)]">stream</span> : null}
                  <span className={item.success ? 'rounded-lg bg-[rgba(31,157,104,0.12)] px-2 py-1 text-[11px] text-[var(--success)]' : 'rounded-lg bg-[rgba(217,111,93,0.12)] px-2 py-1 text-[11px] text-[var(--danger)]'}>
                    {item.success ? (locale === 'zh-CN' ? '成功' : 'Success') : (locale === 'zh-CN' ? '失败' : 'Failed')}
                  </span>
                </div>
                <button type="button" className="inline-flex h-9 items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-sm text-[var(--text)]" onClick={() => setDetailId(item.id)}>
                  <Search size={14} />
                  {locale === 'zh-CN' ? '详情' : 'Detail'}
                </button>
              </div>

              <div className="grid gap-2 text-sm text-[var(--muted)] md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
                  <p className="text-xs">group</p>
                  <p className="mt-1 truncate text-[var(--text)]">{item.matched_group_name || (locale === 'zh-CN' ? '未命中' : 'No match')}</p>
                </div>
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
                  <p className="text-xs">channel</p>
                  <p className="mt-1 truncate text-[var(--text)]">{item.channel_name || item.channel_id || 'n/a'}</p>
                </div>
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
                  <p className="text-xs">token</p>
                  <p className="mt-1 text-[var(--text)]">{item.total_tokens.toLocaleString()}</p>
                </div>
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
                  <p className="text-xs">cost</p>
                  <p className="mt-1 text-[var(--text)]">{formatMoney(item.total_cost_usd)}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--muted)]">
                <span className="inline-flex items-center gap-1.5"><Zap size={13} />{locale === 'zh-CN' ? '首字' : 'First token'} {formatMs(item.first_token_latency_ms)}</span>
                <span className="inline-flex items-center gap-1.5"><Clock3 size={13} />{locale === 'zh-CN' ? '总耗时' : 'Total'} {formatMs(item.latency_ms)}</span>
                <span>{new Date(item.created_at).toLocaleString(locale === 'zh-CN' ? 'zh-CN' : 'en-US')}</span>
              </div>

              {item.error_message ? (
                <div className="rounded-2xl border border-[rgba(217,111,93,0.16)] bg-[rgba(217,111,93,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
                  <div className="flex items-start gap-2">
                    <AlertCircle size={15} className="mt-0.5 shrink-0" />
                    <span>{item.error_message}</span>
                  </div>
                </div>
              ) : null}
            </div>
          </article>
        ))}
        {!isLoading && visibleData.length === 0 ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '暂无请求日志。' : 'No request logs yet.'}</p> : null}
      </div>

      <Dialog.Root open={detailId !== null} onOpenChange={(open) => { if (!open) setDetailId(null) }}>
        <AppDialogContent className="max-w-6xl" title={locale === 'zh-CN' ? '请求详情' : 'Request detail'}>
          {detailLoading || !detail ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载详情...' : 'Loading detail...'}</p> : (
            <div className="grid gap-4">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
                  <p className="text-xs">channel</p>
                  <p className="mt-1 text-[var(--text)]">{detail.channel_name || detail.channel_id || 'n/a'}</p>
                </div>
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
                  <p className="text-xs">status</p>
                  <p className="mt-1 text-[var(--text)]">{detail.status_code}</p>
                </div>
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
                  <p className="text-xs">input/output</p>
                  <p className="mt-1 text-[var(--text)]">{detail.input_tokens.toLocaleString()} / {detail.output_tokens.toLocaleString()}</p>
                </div>
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
                  <p className="text-xs">cost</p>
                  <p className="mt-1 text-[var(--text)]">{formatMoney(detail.total_cost_usd)}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 rounded-2xl bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
                <span className="inline-flex items-center gap-1.5"><Zap size={14} className="text-[rgb(154,101,35)]" />{locale === 'zh-CN' ? '首字时间' : 'First token'}: {formatMs(detail.first_token_latency_ms)}</span>
                <span className="inline-flex items-center gap-1.5"><Clock3 size={14} />{locale === 'zh-CN' ? '总耗时' : 'Total time'}: {formatMs(detail.latency_ms)}</span>
                <span className="inline-flex items-center gap-1.5"><ArrowDownToLine size={14} />{locale === 'zh-CN' ? '输入' : 'Input'}: {detail.input_tokens.toLocaleString()}</span>
                <span className="inline-flex items-center gap-1.5"><ArrowUpFromLine size={14} />{locale === 'zh-CN' ? '输出' : 'Output'}: {detail.output_tokens.toLocaleString()}</span>
                <span className="inline-flex items-center gap-1.5"><DollarSign size={14} />{locale === 'zh-CN' ? '费用' : 'Cost'}: {formatMoney(detail.total_cost_usd)}</span>
              </div>

              <div className="rounded-2xl border border-[var(--line)] bg-[var(--panel-strong)] p-4">
                <p className="text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '尝试链路' : 'Attempts'}</p>
                <div className="mt-3 grid gap-2">
                  {(detail.attempts.length ? detail.attempts : [{ channel_id: detail.channel_id || 'n/a', channel_name: detail.channel_name || detail.channel_id || 'n/a', model_name: detail.resolved_model || detail.requested_model || null, status_code: detail.status_code, success: detail.success, duration_ms: detail.latency_ms, error_message: detail.error_message || null }]).map((attempt, index) => (
                    <div key={`${attempt.channel_id}-${index}`} className="rounded-2xl bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-[var(--text)]">{attempt.channel_name}</span>
                          {attempt.model_name ? <span>{attempt.model_name}</span> : null}
                          <span className={attempt.success ? 'rounded-lg bg-[rgba(31,157,104,0.12)] px-2 py-1 text-[11px] text-[var(--success)]' : 'rounded-lg bg-[rgba(217,111,93,0.12)] px-2 py-1 text-[11px] text-[var(--danger)]'}>{attempt.success ? (locale === 'zh-CN' ? '成功' : 'Success') : (locale === 'zh-CN' ? '失败' : 'Failed')}</span>
                        </div>
                        <div className="flex items-center gap-3 text-xs">
                          <span>{attempt.status_code ?? '-'}</span>
                          <span>{formatMs(attempt.duration_ms)}</span>
                        </div>
                      </div>
                      {attempt.error_message ? <p className="mt-2 text-xs text-[var(--danger)]">{attempt.error_message}</p> : null}
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--panel-strong)]">
                  <div className="border-b border-[var(--line)] px-4 py-3 text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '输入 JSON' : 'Input JSON'}</div>
                  <JsonPanel content={detail.request_content} emptyText={locale === 'zh-CN' ? '无输入内容' : 'No request content'} />
                </div>
                <div className="overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--panel-strong)]">
                  <div className="border-b border-[var(--line)] px-4 py-3 text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '输出 JSON' : 'Output JSON'}</div>
                  <JsonPanel content={detail.response_content} emptyText={locale === 'zh-CN' ? '无输出内容' : 'No response content'} />
                </div>
              </div>
            </div>
          )}
        </AppDialogContent>
      </Dialog.Root>
    </section>
  )
}
