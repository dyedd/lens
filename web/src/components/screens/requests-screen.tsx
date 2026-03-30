"use client"

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { RequestLogItem, apiRequest } from '@/lib/api'

export function RequestsScreen() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['request-logs'],
    queryFn: () => apiRequest<RequestLogItem[]>('/request-logs')
  })

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent-2)]">Requests</p>
          <h2 className="mt-2 text-4xl font-semibold">Recent proxy requests, provider outcomes, and failure context</h2>
        </div>
        <button className="rounded-full border border-[var(--line)] px-4 py-2 text-sm text-[var(--muted)] hover:bg-[var(--panel-strong)]" type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ['request-logs'] })}>
          Refresh
        </button>
      </div>
      <div className="grid gap-3">
        {isLoading ? <p className="text-sm text-[var(--muted)]">Loading request logs...</p> : null}
        {data?.map((item) => (
          <div key={item.id} className="rounded-[24px] border border-[var(--line)] bg-[var(--panel-strong)] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <strong>{item.protocol}</strong>
                <p className="mt-2 text-sm text-[var(--muted)]">model: {item.requested_model || 'n/a'} · group: {item.matched_group_name || 'none'}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">provider: {item.provider_id || 'none'} · key: {item.gateway_key_id || 'none'}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">status: {item.status_code} · latency: {item.latency_ms} ms · {item.success ? 'success' : 'failed'}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">{new Date(item.created_at).toLocaleString()}</p>
                {item.error_message ? <p className="mt-2 text-sm text-[var(--danger)]">{item.error_message}</p> : null}
              </div>
            </div>
          </div>
        ))}
        {!isLoading && (data?.length ?? 0) === 0 ? <p className="text-sm text-[var(--muted)]">No request logs yet.</p> : null}
      </div>
    </section>
  )
}
