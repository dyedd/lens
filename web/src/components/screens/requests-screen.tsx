"use client"

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { RequestLogItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

export function RequestsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const { data, isLoading } = useQuery({
    queryKey: ['request-logs'],
    queryFn: () => apiRequest<RequestLogItem[]>('/request-logs')
  })

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-[36px] font-semibold tracking-[-0.04em] text-[var(--text)]">{locale === 'zh-CN' ? '请求' : 'Requests'}</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            {locale === 'zh-CN' ? '查看最近请求、命中渠道、耗时与失败上下文。' : 'Inspect recent requests, routed providers, latency, and failure context.'}
          </p>
        </div>
        <button className="inline-flex h-10 items-center rounded-full border border-[var(--line)] bg-[var(--panel-strong)] px-4 text-sm text-[var(--text)] shadow-[var(--shadow-sm)]" type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ['request-logs'] })}>
          {locale === 'zh-CN' ? '刷新' : 'Refresh'}
        </button>
      </div>

      <div className="grid gap-3">
        {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载请求日志...' : 'Loading request logs...'}</p> : null}
        {data?.map((item) => (
          <div key={item.id} className="rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
            <div className="grid gap-2">
              <div className="flex flex-wrap items-center gap-3">
                <strong className="text-sm font-semibold">{item.protocol}</strong>
                <span className={item.success ? 'rounded-full bg-[rgba(31,157,104,0.12)] px-3 py-1 text-[11px] text-[var(--success)]' : 'rounded-full bg-[rgba(192,58,76,0.12)] px-3 py-1 text-[11px] text-[var(--danger)]'}>
                  {item.success ? (locale === 'zh-CN' ? '成功' : 'Success') : (locale === 'zh-CN' ? '失败' : 'Failed')}
                </span>
              </div>
              <p className="text-sm text-[var(--muted)]">model: {item.requested_model || 'n/a'} · group: {item.matched_group_name || (locale === 'zh-CN' ? '无' : 'none')}</p>
              <p className="text-sm text-[var(--muted)]">provider: {item.provider_id || 'n/a'} · key: {item.gateway_key_id || 'n/a'}</p>
              <p className="text-sm text-[var(--muted)]">status: {item.status_code} · latency: {item.latency_ms} ms · {new Date(item.created_at).toLocaleString(locale === 'zh-CN' ? 'zh-CN' : 'en-US')}</p>
              {item.error_message ? <p className="text-sm text-[var(--danger)]">{item.error_message}</p> : null}
            </div>
          </div>
        ))}
        {!isLoading && (data?.length ?? 0) === 0 ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '暂无请求日志。' : 'No request logs yet.'}</p> : null}
      </div>
    </section>
  )
}
