"use client"

import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Clock3, Filter, RefreshCcw } from 'lucide-react'
import { RequestLogItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

export function RequestsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const [showFailedOnly, setShowFailedOnly] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: ['request-logs'],
    queryFn: () => apiRequest<RequestLogItem[]>('/request-logs')
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
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <strong className="font-semibold text-[var(--text)]">{item.requested_model || 'n/a'}</strong>
                <span className="text-[var(--muted)]">→</span>
                <span className="rounded-lg bg-[var(--panel)] px-2 py-1 text-[12px] text-[var(--text)]">{item.protocol}</span>
                <span className={item.success ? 'rounded-lg bg-[rgba(31,157,104,0.12)] px-2 py-1 text-[11px] text-[var(--success)]' : 'rounded-lg bg-[rgba(217,111,93,0.12)] px-2 py-1 text-[11px] text-[var(--danger)]'}>
                  {item.success ? (locale === 'zh-CN' ? '成功' : 'Success') : (locale === 'zh-CN' ? '失败' : 'Failed')}
                </span>
              </div>

              <div className="grid gap-2 text-sm text-[var(--muted)] md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
                  <p className="text-xs">group</p>
                  <p className="mt-1 truncate text-[var(--text)]">{item.matched_group_name || (locale === 'zh-CN' ? '未命中' : 'No match')}</p>
                </div>
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
                  <p className="text-xs">channel</p>
                  <p className="mt-1 truncate text-[var(--text)]">{item.channel_id || 'n/a'}</p>
                </div>
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
                  <p className="text-xs">{locale === 'zh-CN' ? '调用密钥' : 'Client key'}</p>
                  <p className="mt-1 truncate text-[var(--text)]">{item.gateway_key_id || 'n/a'}</p>
                </div>
                <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
                  <p className="text-xs">status</p>
                  <p className="mt-1 text-[var(--text)]">{item.status_code}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--muted)]">
                <span className="inline-flex items-center gap-1.5"><Clock3 size={13} />{item.latency_ms} ms</span>
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
    </section>
  )
}

