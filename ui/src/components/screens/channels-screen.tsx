"use client"

import { FormEvent, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, CheckCircle2, Clock3, DollarSign, FileText, Globe, KeyRound, Pencil, Plus, RefreshCcw, Search, ShieldCheck, Trash2, X, XCircle } from 'lucide-react'
import { ApiError, Provider, ProtocolKind, ProviderKeyItem, ProviderModelFetchPayload, ProviderPayload, ProviderStatus, ProviderUrlItem, RequestLogItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/cn'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { SegmentedControl } from '@/components/ui/segmented-control'

type ViewMode = 'cards' | 'list'

type HeaderItem = {
  key: string
  value: string
}

type FormState = {
  name: string
  protocol: ProtocolKind
  base_urls: ProviderUrlItem[]
  keys: ProviderKeyItem[]
  model_patterns: string
  channel_proxy: string
  headers: HeaderItem[]
  match_regex: string
  param_override: string
}

type ProviderStats = {
  requestCount: number
  successCount: number
  failedCount: number
  totalTokens: number
  totalCostUsd: number
  avgLatencyMs: number
}

const protocolOptions: Array<{ value: ProtocolKind; label: string }> = [
  { value: 'openai_chat', label: 'OpenAI Chat' },
  { value: 'openai_responses', label: 'OpenAI Responses' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
]

const emptyForm: FormState = {
  name: '',
  protocol: 'openai_chat',
  base_urls: [{ url: '', delay: 0 }],
  keys: [{ key: '', remark: '', enabled: true }],
  model_patterns: '',
  channel_proxy: '',
  headers: [{ key: '', value: '' }],
  match_regex: '',
  param_override: '',
}

function inputClassName() {
  return 'h-10 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function textareaClassName() {
  return 'min-h-24 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function panelClassName() {
  return 'rounded-[24px] border border-[var(--line)] bg-[var(--panel)]'
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-2">
      <span className="text-sm text-[var(--muted)]">{label}</span>
      {children}
    </label>
  )
}

function splitModelPatterns(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

function joinModelPatterns(items: string[]) {
  return items.join('\n')
}

function mergeUniqueModels(current: string[], next: string[]) {
  return Array.from(new Set([...current, ...next].map((item) => item.trim()).filter(Boolean)))
}

function switchTrackClassName(checked: boolean) {
  return cn(
    'relative h-6 w-11 rounded-full transition-colors duration-200',
    checked ? 'bg-[var(--accent)]' : 'bg-[var(--line-strong)]'
  )
}

function switchThumbClassName(checked: boolean) {
  return cn(
    'absolute top-1 h-4 w-4 rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,0.18)] transition-all duration-200',
    checked ? 'right-1' : 'left-1'
  )
}

function SwitchButton({ checked, onChange, disabled = false }: { checked: boolean; onChange: (checked: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(switchTrackClassName(checked), 'disabled:cursor-not-allowed disabled:opacity-60')}
    >
      <span className={switchThumbClassName(checked)} />
    </button>
  )
}

function SwitchIndicator({ checked }: { checked: boolean }) {
  return (
    <span className={switchTrackClassName(checked)} aria-hidden="true">
      <span className={switchThumbClassName(checked)} />
    </span>
  )
}

function toForm(item: Provider): FormState {
  return {
    name: item.name,
    protocol: item.protocol,
    base_urls: item.base_urls.length ? item.base_urls : [{ url: item.base_url, delay: 0 }],
    keys: item.keys.length ? item.keys : [{ key: item.api_key, remark: '', enabled: true }],
    model_patterns: item.model_patterns.join('\n'),
    channel_proxy: item.channel_proxy,
    headers: Object.entries(item.headers).length
      ? Object.entries(item.headers).map(([key, value]) => ({ key, value }))
      : [{ key: '', value: '' }],
    match_regex: item.match_regex,
    param_override: item.param_override,
  }
}

function toPayload(form: FormState, status: ProviderStatus): ProviderPayload {
  const baseUrls = form.base_urls.map((item) => ({ url: item.url.trim(), delay: Number(item.delay) || 0 })).filter((item) => item.url)
  const keys = form.keys.map((item) => ({ key: item.key.trim(), remark: item.remark.trim(), enabled: item.enabled })).filter((item) => item.key)
  const headers = Object.fromEntries(form.headers.map((item) => [item.key.trim(), item.value] as const).filter(([key]) => key))

  return {
    name: form.name.trim(),
    protocol: form.protocol,
    base_url: (baseUrls[0]?.url ?? '').trim(),
    api_key: (keys.find((item) => item.enabled)?.key ?? keys[0]?.key ?? '').trim(),
    status,
    headers,
    model_patterns: splitModelPatterns(form.model_patterns),
    base_urls: baseUrls,
    keys,
    proxy: Boolean(form.channel_proxy.trim()),
    channel_proxy: form.channel_proxy.trim(),
    param_override: form.param_override.trim(),
    match_regex: form.match_regex.trim(),
  }
}

function maskKey(value: string) {
  if (value.length <= 10) return value
  return value.slice(0, 6) + '...' + value.slice(-4)
}

function formatCompact(value: number) {
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(2) + 'M'
  if (value >= 1_000) return (value / 1_000).toFixed(2) + 'K'
  return String(value)
}

function formatMoney(value: number) {
  if (value <= 0) return '$0.00'
  return '$' + value.toFixed(value < 1 ? 4 : 2)
}

function protocolLabel(protocol: ProtocolKind) {
  return protocolOptions.find((item) => item.value === protocol)?.label ?? protocol
}

function providerEndpoint(provider: Provider) {
  return provider.base_urls[0]?.url ?? provider.base_url
}

function enabledKeyCount(provider: Provider) {
  return provider.keys.filter((item) => item.enabled).length
}

function buildStats(logs: RequestLogItem[] | undefined) {
  const grouped = new Map<string, ProviderStats>()
  for (const item of logs ?? []) {
    if (!item.provider_id) continue
    const current = grouped.get(item.provider_id) ?? { requestCount: 0, successCount: 0, failedCount: 0, totalTokens: 0, totalCostUsd: 0, avgLatencyMs: 0 }
    current.requestCount += 1
    current.successCount += item.success ? 1 : 0
    current.failedCount += item.success ? 0 : 1
    current.totalTokens += item.total_tokens
    current.totalCostUsd += item.total_cost_usd
    current.avgLatencyMs += item.latency_ms
    grouped.set(item.provider_id, current)
  }
  for (const [providerId, value] of grouped.entries()) {
    grouped.set(providerId, { ...value, avgLatencyMs: value.requestCount ? Math.round(value.avgLatencyMs / value.requestCount) : 0 })
  }
  return grouped
}

function MetricCard({ icon, label, value, accent = false }: { icon: React.ReactNode; label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel)] p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-[var(--muted)]">{icon}{label}</div>
      <div className={accent ? 'mt-3 text-[26px] font-semibold text-[var(--accent)]' : 'mt-3 text-[26px] font-semibold text-[var(--text)]'}>{value}</div>
    </div>
  )
}

export function ChannelsScreen() {
  const queryClient = useQueryClient()
  const { locale, t } = useI18n()
  const [viewMode, setViewMode] = useState<ViewMode>('cards')
  const [search, setSearch] = useState('')
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingStatus, setEditingStatus] = useState<ProviderStatus>('enabled')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [detailTarget, setDetailTarget] = useState<Provider | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Provider | null>(null)
  const [fetchingModels, setFetchingModels] = useState(false)
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [pickerSelectedModels, setPickerSelectedModels] = useState<string[]>([])

  const { data: providers, isLoading } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })
  const { data: requestLogs } = useQuery({ queryKey: ['request-logs'], queryFn: () => apiRequest<RequestLogItem[]>('/request-logs') })

  const providerStats = useMemo(() => buildStats(requestLogs), [requestLogs])

  const visibleData = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) return providers ?? []
    return (providers ?? []).filter((item) => {
      const models = item.model_patterns.join(' ').toLowerCase()
      const urls = item.base_urls.map((entry) => entry.url).join(' ').toLowerCase()
      return item.name.toLowerCase().includes(keyword) || models.includes(keyword) || urls.includes(keyword)
    })
  }, [providers, search])

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['providers'] }),
      queryClient.invalidateQueries({ queryKey: ['request-logs'] }),
    ])
  }

  function openCreate() {
    setEditingId(null)
    setEditingStatus('enabled')
    setForm(emptyForm)
    setError('')
    setDetailTarget(null)
    setDialogOpen(true)
  }

  function openEdit(item: Provider) {
    setEditingId(item.id)
    setEditingStatus(item.status)
    setForm(toForm(item))
    setError('')
    setDetailTarget(null)
    setDialogOpen(true)
  }

  async function saveProvider(providerId: string | null) {
    await apiRequest<Provider>(providerId ? '/providers/' + providerId : '/providers', {
      method: providerId ? 'PUT' : 'POST',
      body: JSON.stringify(toPayload(form, editingStatus)),
    })
    await refresh()
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      await saveProvider(editingId)
      setDialogOpen(false)
      setEditingId(null)
      setEditingStatus('enabled')
      setForm(emptyForm)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存渠道失败' : 'Failed to save channel'))
    }
  }

  async function toggleStatus(item: Provider) {
    setBusyId(item.id)
    setError('')
    try {
      await apiRequest<Provider>('/providers/' + item.id, {
        method: 'PUT',
        body: JSON.stringify({ status: item.status === 'enabled' ? 'disabled' : 'enabled' }),
      })
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '更新渠道状态失败' : 'Failed to update status'))
    } finally {
      setBusyId(null)
    }
  }

  async function remove(item: Provider) {
    setBusyId(item.id)
    setError('')
    try {
      await apiRequest<void>('/providers/' + item.id, { method: 'DELETE' })
      setDeleteTarget(null)
      setDetailTarget(null)
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除渠道失败' : 'Failed to delete channel'))
    } finally {
      setBusyId(null)
    }
  }

  function updateBaseUrl(index: number, patch: Partial<ProviderUrlItem>) {
    setForm((current) => ({ ...current, base_urls: current.base_urls.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) }))
  }

  function updateKey(index: number, patch: Partial<ProviderKeyItem>) {
    setForm((current) => ({ ...current, keys: current.keys.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) }))
  }

  function updateHeader(index: number, patch: Partial<HeaderItem>) {
    setForm((current) => ({ ...current, headers: current.headers.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) }))
  }

  const detailStats = detailTarget ? providerStats.get(detailTarget.id) : undefined
  const formModels = useMemo(() => splitModelPatterns(form.model_patterns), [form.model_patterns])

  function upsertModels(items: string[]) {
    setForm((current) => ({ ...current, model_patterns: joinModelPatterns(items) }))
  }

  function removeModel(value: string) {
    upsertModels(formModels.filter((item) => item !== value))
  }

  function togglePickerModel(value: string) {
    setPickerSelectedModels((current) => current.includes(value) ? current.filter((item) => item !== value) : [...current, value])
  }

  function confirmModelSelection() {
    upsertModels(mergeUniqueModels(formModels, pickerSelectedModels))
    setModelPickerOpen(false)
  }

  async function fetchModels() {
    setFetchingModels(true)
    setError('')
    try {
      const payload: ProviderModelFetchPayload = {
        protocol: form.protocol,
        base_url: form.base_urls[0]?.url?.trim() ?? '',
        api_key: form.keys.find((item) => item.enabled && item.key.trim())?.key.trim() ?? form.keys[0]?.key.trim() ?? '',
        headers: Object.fromEntries(form.headers.map((item) => [item.key.trim(), item.value] as const).filter(([key]) => key)),
        base_urls: form.base_urls.map((item) => ({ url: item.url.trim(), delay: Number(item.delay) || 0 })).filter((item) => item.url),
        keys: form.keys.map((item) => ({ key: item.key.trim(), remark: item.remark.trim(), enabled: item.enabled })).filter((item) => item.key),
        channel_proxy: form.channel_proxy.trim(),
        match_regex: form.match_regex.trim(),
      }
      const models = await apiRequest<string[]>('/providers/fetch-models', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setAvailableModels(models)
      setPickerSelectedModels(formModels.filter((item) => models.includes(item)))
      setModelPickerOpen(true)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '刷新模型失败' : 'Failed to refresh models'))
    } finally {
      setFetchingModels(false)
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2 text-[var(--muted)]">
        <div className="hidden h-9 items-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 md:flex">
          <Search size={15} />
          <input className="ml-2 w-44 bg-transparent text-sm outline-none" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索渠道 / 模型 / 地址' : 'Search channels'} />
        </div>
        <SegmentedControl value={viewMode} onValueChange={setViewMode} options={[{ value: 'cards', label: locale === 'zh-CN' ? '卡片' : 'Cards' }, { value: 'list', label: locale === 'zh-CN' ? '列表' : 'List' }]} />
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={() => void refresh()} title={t.refresh}>
          <RefreshCcw size={16} />
        </button>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={openCreate} title={locale === 'zh-CN' ? '新增渠道' : 'New channel'}>
          <Plus size={16} />
        </button>
      </div>

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载渠道...' : 'Loading channels...'}</p> : null}

      {viewMode === 'cards' ? (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {visibleData.map((item) => {
            const stats = providerStats.get(item.id)
            return (
              <article key={item.id} className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--panel-soft)]">
                <div className="flex items-start justify-between gap-3">
                  <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setDetailTarget(item)}>
                    <div className="truncate text-[17px] font-semibold text-[var(--text)]">{item.name}</div>
                  </button>
                  <div className="flex items-center gap-1.5">
                    <button type="button" onClick={() => void toggleStatus(item)} disabled={busyId === item.id} className={item.status === 'enabled' ? 'relative h-6 w-11 rounded-full bg-[var(--accent)] disabled:opacity-60' : 'relative h-6 w-11 rounded-full bg-[var(--line-strong)] disabled:opacity-60'}>
                      <span className={item.status === 'enabled' ? 'absolute right-1 top-1 h-4 w-4 rounded-full bg-white' : 'absolute left-1 top-1 h-4 w-4 rounded-full bg-white'} />
                    </button>
                    <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--text)]" onClick={() => openEdit(item)}><Pencil size={15} /></button>
                    <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--danger)] transition hover:bg-[rgba(217,111,93,0.08)]" onClick={() => setDeleteTarget(item)}><Trash2 size={15} /></button>
                  </div>
                </div>

                <button type="button" className="mt-4 grid w-full gap-3 text-left" onClick={() => setDetailTarget(item)}>
                  <div className="flex items-center justify-between rounded-[22px] border border-[var(--line)] bg-[var(--panel)] p-3">
                    <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(37,99,235,0.12)] text-[var(--accent)]"><Activity className="h-4 w-4" /></span><span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '请求数' : 'Requests'}</span></div>
                    <strong className="text-base text-[var(--text)]">{formatCompact(stats?.requestCount ?? 0)}</strong>
                  </div>
                  <div className="flex items-center justify-between rounded-[22px] border border-[var(--line)] bg-[var(--panel)] p-3">
                    <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(37,99,235,0.12)] text-[var(--accent)]"><DollarSign className="h-4 w-4" /></span><span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '成本' : 'Cost'}</span></div>
                    <strong className="text-base text-[var(--text)]">{formatMoney(stats?.totalCostUsd ?? 0)}</strong>
                  </div>
                </button>
              </article>
            )
          })}
        </div>
      ) : (
        <div className="overflow-hidden rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] shadow-[var(--shadow-sm)]">
          <div className="grid grid-cols-[minmax(0,1.2fr)_1fr_110px_130px_140px] gap-4 border-b border-[var(--line)] px-5 py-3 text-xs font-semibold text-[var(--muted)]">
            <span>{locale === 'zh-CN' ? '渠道' : 'Channel'}</span>
            <span>{locale === 'zh-CN' ? '地址 / 模型' : 'Endpoint / Models'}</span>
            <span>{locale === 'zh-CN' ? '请求数' : 'Requests'}</span>
            <span>{locale === 'zh-CN' ? '密钥' : 'Keys'}</span>
            <span>{locale === 'zh-CN' ? '操作' : 'Actions'}</span>
          </div>
          <div className="divide-y divide-[var(--line)]">
            {visibleData.map((item) => {
              const stats = providerStats.get(item.id)
              return (
                <div key={item.id} className="grid grid-cols-[minmax(0,1.2fr)_1fr_110px_130px_140px] gap-4 px-5 py-4 text-sm text-[var(--text)]">
                  <button type="button" className="min-w-0 text-left" onClick={() => setDetailTarget(item)}>
                    <div className="truncate font-semibold">{item.name}</div>
                    <div className="mt-1 text-xs text-[var(--muted)]">{item.status === 'enabled' ? (locale === 'zh-CN' ? '已启用' : 'Enabled') : (locale === 'zh-CN' ? '已停用' : 'Disabled')}</div>
                  </button>
                  <button type="button" className="min-w-0 text-left" onClick={() => setDetailTarget(item)}>
                    <div className="truncate text-xs text-[var(--muted)]">{providerEndpoint(item)}</div>
                    <div className="mt-1 truncate">{item.model_patterns.slice(0, 2).join(' / ') || (locale === 'zh-CN' ? '未配置模型' : 'No models')}</div>
                  </button>
                  <div className="flex items-center text-[var(--muted)]">{formatCompact(stats?.requestCount ?? 0)}</div>
                  <div className="flex items-center text-[var(--muted)]">{enabledKeyCount(item)}/{item.keys.length}</div>
                  <div className="flex items-center justify-end gap-2">
                    <button type="button" onClick={() => void toggleStatus(item)} disabled={busyId === item.id} className={item.status === 'enabled' ? 'relative h-6 w-11 rounded-full bg-[var(--accent)] disabled:opacity-60' : 'relative h-6 w-11 rounded-full bg-[var(--line-strong)] disabled:opacity-60'}><span className={item.status === 'enabled' ? 'absolute right-1 top-1 h-4 w-4 rounded-full bg-white' : 'absolute left-1 top-1 h-4 w-4 rounded-full bg-white'} /></button>
                    <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--text)]" onClick={() => openEdit(item)}><Pencil size={15} /></button>
                    <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--danger)] transition hover:bg-[rgba(217,111,93,0.08)]" onClick={() => setDeleteTarget(item)}><Trash2 size={15} /></button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <Dialog.Root open={Boolean(detailTarget)} onOpenChange={(open) => { if (!open) setDetailTarget(null) }}>
        {detailTarget ? (
          <AppDialogContent className="max-w-5xl" title={locale === 'zh-CN' ? '渠道详情' : 'Channel detail'}>
            <div className="space-y-5">
              <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
                <MetricCard icon={<Activity className="h-4 w-4 text-[var(--accent)]" />} label={locale === 'zh-CN' ? '总请求' : 'Requests'} value={formatCompact(detailStats?.requestCount ?? 0)} accent />
                <MetricCard icon={<CheckCircle2 className="h-4 w-4 text-[var(--accent)]" />} label={locale === 'zh-CN' ? '成功' : 'Success'} value={formatCompact(detailStats?.successCount ?? 0)} />
                <MetricCard icon={<XCircle className="h-4 w-4 text-[var(--danger)]" />} label={locale === 'zh-CN' ? '失败' : 'Failed'} value={formatCompact(detailStats?.failedCount ?? 0)} />
                <MetricCard icon={<FileText className="h-4 w-4 text-[var(--accent)]" />} label="Token" value={formatCompact(detailStats?.totalTokens ?? 0)} />
                <MetricCard icon={<DollarSign className="h-4 w-4 text-[var(--accent)]" />} label={locale === 'zh-CN' ? '成本' : 'Cost'} value={formatMoney(detailStats?.totalCostUsd ?? 0)} />
                <MetricCard icon={<Clock3 className="h-4 w-4 text-[var(--accent)]" />} label={locale === 'zh-CN' ? '平均耗时' : 'Latency'} value={`${detailStats?.avgLatencyMs ?? 0} ms`} />
              </div>
              <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
                <section className="space-y-4">
                  <div className={panelClassName()}>
                    <div className="flex items-center gap-2 border-b border-[var(--line)] px-4 py-3 text-sm font-semibold text-[var(--text)]"><Globe className="h-4 w-4 text-[var(--muted)]" />Base URLs</div>
                    {detailTarget.base_urls.map((item, index) => <div key={item.url + index} className="flex items-center justify-between gap-4 border-b border-[var(--line)] px-4 py-3 last:border-b-0"><div className="min-w-0 truncate font-mono text-sm text-[var(--text)]">{item.url}</div><span className="whitespace-nowrap text-xs text-[var(--muted)]">{item.delay} ms</span></div>)}
                  </div>
                  <div className={panelClassName()}>
                    <div className="flex items-center gap-2 border-b border-[var(--line)] px-4 py-3 text-sm font-semibold text-[var(--text)]"><KeyRound className="h-4 w-4 text-[var(--muted)]" />API Keys</div>
                    {detailTarget.keys.map((item, index) => <div key={item.key + index} className="flex items-center justify-between gap-4 border-b border-[var(--line)] px-4 py-3 last:border-b-0"><div className="min-w-0"><div className="truncate font-mono text-sm text-[var(--text)]">{maskKey(item.key)}</div>{item.remark ? <div className="mt-1 text-xs text-[var(--muted)]">{item.remark}</div> : null}</div><span className={item.enabled ? 'text-xs text-[var(--accent)]' : 'text-xs text-[var(--muted)]'}>{item.enabled ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}</span></div>)}
                  </div>
                </section>
                <section className="space-y-4">
                  <div className={panelClassName()}>
                    <div className="flex items-center gap-2 border-b border-[var(--line)] px-4 py-3 text-sm font-semibold text-[var(--text)]"><ShieldCheck className="h-4 w-4 text-[var(--muted)]" />{locale === 'zh-CN' ? '基础信息' : 'Overview'}</div>
                    <div className="grid gap-3 px-4 py-4 text-sm text-[var(--text)]">
                      <div><div className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '协议' : 'Protocol'}</div><div className="mt-1">{protocolLabel(detailTarget.protocol)}</div></div>
                      <div><div className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '模型规则' : 'Model rules'}</div><div className="mt-1 break-all">{detailTarget.model_patterns.join('、') || (locale === 'zh-CN' ? '未配置' : 'Not configured')}</div></div>
                      <div><div className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '代理' : 'Proxy'}</div><div className="mt-1">{detailTarget.proxy ? (detailTarget.channel_proxy || (locale === 'zh-CN' ? '已启用' : 'Enabled')) : (locale === 'zh-CN' ? '未启用' : 'Disabled')}</div></div>
                      <div><div className="text-xs text-[var(--muted)]">Match Regex</div><div className="mt-1 break-all">{detailTarget.match_regex || (locale === 'zh-CN' ? '未配置' : 'Not configured')}</div></div>
                    </div>
                  </div>
                  <div className={panelClassName()}>
                    <div className="flex items-center gap-2 border-b border-[var(--line)] px-4 py-3 text-sm font-semibold text-[var(--text)]"><FileText className="h-4 w-4 text-[var(--muted)]" />Headers / Param Override</div>
                    <div className="grid gap-4 px-4 py-4 text-sm text-[var(--text)]">
                      <div><div className="text-xs text-[var(--muted)]">Headers</div><div className="mt-1 space-y-1">{Object.entries(detailTarget.headers).length ? Object.entries(detailTarget.headers).map(([key, value]) => <div key={key} className="break-all font-mono text-xs">{key}: {value}</div>) : <div className="text-[var(--muted)]">{locale === 'zh-CN' ? '未配置' : 'Not configured'}</div>}</div></div>
                      <div><div className="text-xs text-[var(--muted)]">Param Override</div><div className="mt-1 whitespace-pre-wrap break-all text-xs text-[var(--text)]">{detailTarget.param_override || (locale === 'zh-CN' ? '未配置' : 'Not configured')}</div></div>
                    </div>
                  </div>
                </section>
              </div>
              <div className="grid gap-3 sm:grid-cols-2"><button className="h-12 rounded-2xl bg-[var(--accent)] text-sm font-medium text-white" type="button" onClick={() => openEdit(detailTarget)}>{locale === 'zh-CN' ? '编辑渠道' : 'Edit channel'}</button><button className="h-12 rounded-2xl bg-[var(--danger)] text-sm font-medium text-white" type="button" onClick={() => setDeleteTarget(detailTarget)}>{locale === 'zh-CN' ? '删除渠道' : 'Delete channel'}</button></div>
            </div>
          </AppDialogContent>
        ) : null}
      </Dialog.Root>

      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent className="max-w-4xl" title={editingId ? (locale === 'zh-CN' ? '编辑渠道' : 'Edit channel') : (locale === 'zh-CN' ? '新建渠道' : 'Create channel')}>
          <form className="grid gap-5" onSubmit={submit}>
            <div className="grid gap-4 md:grid-cols-2"><Field label={locale === 'zh-CN' ? '渠道名称' : 'Channel name'}><input className={inputClassName()} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field><Field label={locale === 'zh-CN' ? '渠道类型' : 'Protocol'}><select className={inputClassName()} value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as ProtocolKind })}>{protocolOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field></div>
            <div className="space-y-2"><div className="flex items-center justify-between"><span className="text-sm text-[var(--muted)]">Base URLs ({form.base_urls.length})</span><button className="text-sm text-[var(--muted)]" type="button" onClick={() => setForm((current) => ({ ...current, base_urls: [...current.base_urls, { url: '', delay: 0 }] }))}>+ {locale === 'zh-CN' ? '添加' : 'Add'}</button></div><div className="space-y-2">{form.base_urls.map((item, index) => <div key={index} className="flex items-center gap-2"><input className={inputClassName()} value={item.url} onChange={(e) => updateBaseUrl(index, { url: e.target.value })} placeholder="https://api.openai.com/v1" /><button className="inline-flex h-10 w-10 items-center justify-center text-[var(--muted)]" type="button" onClick={() => setForm((current) => ({ ...current, base_urls: current.base_urls.length > 1 ? current.base_urls.filter((_, itemIndex) => itemIndex !== index) : current.base_urls }))}>×</button></div>)}</div></div>
            <div className="space-y-2"><div className="flex items-center justify-between"><span className="text-sm text-[var(--muted)]">API Keys ({form.keys.length})</span><button className="text-sm text-[var(--muted)]" type="button" onClick={() => setForm((current) => ({ ...current, keys: [...current.keys, { key: '', remark: '', enabled: true }] }))}>+ {locale === 'zh-CN' ? '添加' : 'Add'}</button></div><div className="space-y-2">{form.keys.map((item, index) => <div key={index} className="grid grid-cols-[minmax(0,1fr)_108px_52px_40px] items-center gap-2"><input className={inputClassName()} value={item.key} onChange={(e) => updateKey(index, { key: e.target.value })} placeholder="sk-..." /><input className={inputClassName()} value={item.remark} onChange={(e) => updateKey(index, { remark: e.target.value })} placeholder={locale === 'zh-CN' ? '备注' : 'Remark'} /><div className="flex justify-center"><SwitchButton checked={item.enabled} onChange={(checked) => updateKey(index, { enabled: checked })} /></div><button className="inline-flex h-10 w-10 items-center justify-center rounded-xl text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--text)]" type="button" onClick={() => setForm((current) => ({ ...current, keys: current.keys.length > 1 ? current.keys.filter((_, itemIndex) => itemIndex !== index) : current.keys }))}>×</button></div>)}</div></div>
            <div className="space-y-3"><div className="flex items-center justify-between"><span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '已选模型' : 'Selected models'}</span><button className="inline-flex h-8 items-center gap-1 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-xs text-[var(--muted)] transition hover:text-[var(--text)] disabled:cursor-not-allowed disabled:opacity-60" type="button" onClick={() => void fetchModels()} disabled={!form.base_urls[0]?.url.trim() || !form.keys.some((item) => item.enabled && item.key.trim()) || fetchingModels}><RefreshCcw size={13} className={fetchingModels ? 'animate-spin' : ''} />{locale === 'zh-CN' ? '刷新模型' : 'Refresh models'}</button></div><div className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-3"><div className="flex flex-wrap gap-2">{formModels.length ? formModels.map((model) => <span key={model} className="inline-flex items-center gap-1 rounded-full bg-[var(--panel-strong)] px-3 py-1.5 text-xs text-[var(--text)]">{model}<button className="text-[var(--muted)] transition hover:text-[var(--text)]" type="button" onClick={() => removeModel(model)}><X size={13} /></button></span>) : <span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '暂无已选模型，请先刷新后勾选。' : 'No selected models yet. Refresh and choose models first.'}</span>}</div></div></div>
            <details className="rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3"><summary className="cursor-pointer text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '高级设置' : 'Advanced settings'}</summary><div className="mt-4 grid gap-4"><Field label={locale === 'zh-CN' ? '渠道代理' : 'Channel proxy'}><input className={inputClassName()} value={form.channel_proxy} onChange={(e) => setForm({ ...form, channel_proxy: e.target.value })} placeholder="http://127.0.0.1:7890" /></Field><div className="space-y-2"><div className="flex items-center justify-between"><span className="text-sm text-[var(--muted)]">Headers</span><button className="text-sm text-[var(--muted)]" type="button" onClick={() => setForm((current) => ({ ...current, headers: [...current.headers, { key: '', value: '' }] }))}>+ {locale === 'zh-CN' ? '添加' : 'Add'}</button></div><div className="space-y-2">{form.headers.map((item, index) => <div key={index} className="flex items-center gap-2"><input className={inputClassName() + ' flex-1'} value={item.key} onChange={(e) => updateHeader(index, { key: e.target.value })} placeholder="Header-Key" /><input className={inputClassName() + ' flex-1'} value={item.value} onChange={(e) => updateHeader(index, { value: e.target.value })} placeholder="Header-Value" /><button className="inline-flex h-10 w-10 items-center justify-center text-[var(--muted)]" type="button" onClick={() => setForm((current) => ({ ...current, headers: current.headers.length > 1 ? current.headers.filter((_, itemIndex) => itemIndex !== index) : current.headers }))}>×</button></div>)}</div></div><Field label="Param Override"><textarea className={textareaClassName()} value={form.param_override} onChange={(e) => setForm({ ...form, param_override: e.target.value })} /></Field></div></details>
            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-3"><button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button><button className="rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white" type="submit">{editingId ? (locale === 'zh-CN' ? '保存渠道' : 'Save channel') : (locale === 'zh-CN' ? '创建渠道' : 'Create channel')}</button></div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除渠道' : 'Delete channel'} description={locale === 'zh-CN' ? '删除后该渠道会从路由池中移除。' : 'This removes the channel from routing pools.'}><div className="grid gap-5"><div className="rounded-2xl bg-[var(--panel)] p-4"><strong>{deleteTarget?.name}</strong><p className="mt-2 text-sm text-[var(--muted)]">{deleteTarget ? providerEndpoint(deleteTarget) : ''}</p></div><div className="flex justify-end gap-3"><button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDeleteTarget(null)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button><button className="rounded-xl bg-[var(--danger)] px-4 py-2.5 text-sm font-medium text-white" type="button" onClick={() => deleteTarget && void remove(deleteTarget)} disabled={busyId === deleteTarget?.id}>{busyId === deleteTarget?.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '确认删除' : 'Delete')}</button></div></div></AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={modelPickerOpen} onOpenChange={setModelPickerOpen}>
        <AppDialogContent className="max-w-2xl" title={locale === 'zh-CN' ? '选择模型' : 'Select models'} description={locale === 'zh-CN' ? '从刷新到的模型列表中勾选要加入当前渠道的模型。' : 'Choose which fetched models should be added to this channel.'}>
          <div className="grid gap-5">
            <div className="max-h-[420px] overflow-y-auto rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-3">
              <div className="grid gap-2 sm:grid-cols-2">
                {availableModels.length ? availableModels.map((model) => {
                  const checked = pickerSelectedModels.includes(model)
                  return (
                    <button key={model} type="button" onClick={() => togglePickerModel(model)} className={cn('flex items-center justify-between rounded-xl border px-3 py-2.5 text-left text-sm transition', checked ? 'border-[var(--accent)] bg-[var(--panel-strong)] text-[var(--text)]' : 'border-[var(--line)] bg-transparent text-[var(--muted)] hover:border-[var(--line-strong)] hover:text-[var(--text)]')}>
                      <span className="truncate pr-3">{model}</span>
                      <SwitchIndicator checked={checked} />
                    </button>
                  )
                }) : <span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '未获取到可用模型。' : 'No models were fetched.'}</span>}
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setModelPickerOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white" type="button" onClick={confirmModelSelection}>{locale === 'zh-CN' ? '加入已选模型' : 'Add selected models'}</button>
            </div>
          </div>
        </AppDialogContent>
      </Dialog.Root>
    </section>
  )
}
