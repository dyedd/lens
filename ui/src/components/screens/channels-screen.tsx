"use client"

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, ChevronDown, Ellipsis, KeyRound, Pencil, Plus, RefreshCcw, Search, Server, Trash2, Waypoints, X } from 'lucide-react'
import {
  ApiError,
  ProtocolKind,
  RequestLogItem,
  Site,
  SiteCredentialInput,
  SiteModelFetchItem,
  SiteModelFetchPayload,
  SitePayload,
  SiteProtocolCredentialBindingInput,
  SiteModelInput,
  apiRequest,
} from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/cn'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { SegmentedControl } from '@/components/ui/segmented-control'

type ViewMode = 'cards' | 'list'

const protocolOptions: Array<{ value: ProtocolKind; label: string }> = [
  { value: 'openai_chat', label: 'OpenAI Chat' },
  { value: 'openai_responses', label: 'OpenAI Responses' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
]

type HeaderItem = { key: string; value: string }
type FormCredential = Omit<SiteCredentialInput, 'id'> & { id: string }

function createCredentialId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `credential-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

type FormProtocol = {
  id?: string | null
  protocol: ProtocolKind
  enabled: boolean
  headers: HeaderItem[]
  channel_proxy: string
  param_override: string
  match_regex: string
  bindings: SiteProtocolCredentialBindingInput[]
  models: SiteModelInput[]
  expanded: boolean
  model_filter_credential_id?: string | null
}

type FormState = {
  name: string
  base_url: string
  credentials: FormCredential[]
  protocols: FormProtocol[]
}

type PickerModelItem = {
  credential_id: string
  model_name: string
}

type SiteStats = {
  requestCount: number
  successCount: number
  failedCount: number
}

type SiteRow = Site & {
  subtitle: string
  protocol_count: number
  credential_count: number
  model_count: number
  endpoint_summary: string
}

type SiteDetailStats = SiteStats & {
  protocolCount: number
  credentialCount: number
  modelCount: number
}

const emptyProtocol = (): FormProtocol => ({
  id: null,
  protocol: 'openai_chat',
  enabled: true,
  headers: [{ key: '', value: '' }],
  channel_proxy: '',
  param_override: '',
  match_regex: '',
  bindings: [],
  models: [],
  expanded: true,
  model_filter_credential_id: null,
})

const emptyForm = (): FormState => ({
  name: '',
  base_url: '',
  credentials: [{ id: createCredentialId(), name: '', api_key: '', enabled: true }],
  protocols: [emptyProtocol()],
})

function inputClassName() {
  return 'h-10 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function textareaClassName() {
  return 'min-h-24 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function panelClassName(extra = '') {
  return cn('rounded-[24px] border border-[var(--line)] bg-[var(--panel)]', extra)
}

function protocolLabel(protocol: ProtocolKind) {
  return protocolOptions.find((item) => item.value === protocol)?.label ?? protocol
}

function maskKey(value: string) {
  if (value.length <= 10) return value
  return `${value.slice(0, 6)}...${value.slice(-4)}`
}

function isGeneratedCredentialName(value: string) {
  const normalized = value.trim().toLowerCase()
  return normalized === '默认密钥' || /^key\s*\d+$/.test(normalized) || /^密钥\s*\d+$/.test(value.trim())
}

function fallbackCredentialName(index: number) {
  return `Key ${index + 1}`
}

function credentialLabel(item: FormCredential, index: number, locale: string) {
  const name = item.name.trim()
  if (name) return name
  return locale === 'zh-CN' ? `密钥 ${index + 1}` : `Key ${index + 1}`
}

function safeText(value: string | null | undefined) {
  return typeof value === 'string' ? value : ''
}

function modelBadgeClassName(enabled: boolean) {
  return enabled
    ? 'inline-flex items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--panel-strong)] px-4 py-2 text-sm font-medium text-[var(--text)] transition hover:border-[var(--line-strong)]'
    : 'inline-flex items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--panel)] px-4 py-2 text-sm font-medium text-[var(--muted)]'
}

function siteSubtitle(site: Site) {
  return site.protocols.map((item) => protocolLabel(item.protocol)).join(' / ')
}

function siteEndpointSummary(site: Site) {
  return site.base_url || ''
}

function siteModelCount(site: Site) {
  return site.protocols.reduce((total, protocol) => total + protocol.models.filter((item) => item.enabled).length, 0)
}

function buildDetailStats(site: Site, stats?: SiteStats): SiteDetailStats {
  return {
    requestCount: stats?.requestCount ?? 0,
    successCount: stats?.successCount ?? 0,
    failedCount: stats?.failedCount ?? 0,
    protocolCount: site.protocols.length,
    credentialCount: site.credentials.length,
    modelCount: siteModelCount(site),
  }
}

function isSiteEnabled(site: Site) {
  return site.protocols.some((item) => item.enabled)
}

function MetricCard({ icon, label, value, tone = 'default' }: { icon: React.ReactNode; label: string; value: string; tone?: 'default' | 'accent' | 'danger' }) {
  const valueClassName = tone === 'accent'
    ? 'text-[var(--accent)]'
    : tone === 'danger'
      ? 'text-[var(--danger)]'
      : 'text-[var(--text)]'

  return (
    <div className="rounded-[22px] border border-[var(--line)] bg-[var(--panel)] px-4 py-4">
      <div className="flex items-center gap-2 text-[13px] font-medium text-[var(--muted)]">{icon}{label}</div>
      <div className={cn('mt-4 text-[18px] font-semibold leading-none sm:text-[22px]', valueClassName)}>{value}</div>
    </div>
  )
}

function buildSiteStats(logs: RequestLogItem[] | undefined, sites: Site[] | undefined) {
  const protocolToSite = new Map<string, string>()
  for (const site of sites ?? []) {
    for (const protocol of site.protocols) {
      protocolToSite.set(protocol.id, site.id)
    }
  }
  const grouped = new Map<string, SiteStats>()
  for (const row of logs ?? []) {
    if (!row.channel_id) continue
    const siteId = protocolToSite.get(row.channel_id)
    if (!siteId) continue
    const current = grouped.get(siteId) ?? { requestCount: 0, successCount: 0, failedCount: 0 }
    current.requestCount += 1
    current.successCount += row.success ? 1 : 0
    current.failedCount += row.success ? 0 : 1
    grouped.set(siteId, current)
  }
  return grouped
}

function toForm(site: Site): FormState {
  return {
    name: site.name,
    base_url: safeText(site.base_url),
    credentials: site.credentials.map((item) => ({ id: item.id, name: isGeneratedCredentialName(item.name) ? '' : item.name, api_key: item.api_key, enabled: item.enabled })),
    protocols: site.protocols.map((item) => ({
      id: item.id,
      protocol: item.protocol,
      enabled: item.enabled,
      headers: Object.entries(item.headers).length ? Object.entries(item.headers).map(([key, value]) => ({ key, value })) : [{ key: '', value: '' }],
      channel_proxy: item.channel_proxy,
      param_override: item.param_override,
      match_regex: safeText(item.match_regex),
      bindings: item.bindings.map((binding) => ({ credential_id: binding.credential_id, enabled: binding.enabled })),
      models: item.models.map((model) => ({ id: model.id, credential_id: model.credential_id, model_name: model.model_name, enabled: model.enabled })),
      expanded: true,
      model_filter_credential_id: null,
    })),
  }
}

function toPayload(form: FormState): SitePayload {
  return {
    name: form.name.trim(),
    base_url: safeText(form.base_url).trim(),
    credentials: form.credentials
      .map((item, index) => ({ id: item.id, name: item.name.trim() || fallbackCredentialName(index), api_key: item.api_key.trim(), enabled: item.enabled }))
      .filter((item) => item.api_key),
    protocols: form.protocols.map((item) => ({
      id: item.id,
      protocol: item.protocol,
      enabled: item.enabled,
      headers: Object.fromEntries(item.headers.map((entry) => [entry.key.trim(), entry.value] as const).filter(([key]) => key)),
      channel_proxy: item.channel_proxy.trim(),
      param_override: item.param_override.trim(),
      match_regex: safeText(item.match_regex).trim(),
      bindings: item.bindings.filter((binding) => binding.credential_id),
      models: item.models.map((model) => ({ id: model.id, credential_id: model.credential_id, model_name: model.model_name.trim(), enabled: model.enabled })).filter((model) => model.credential_id && model.model_name),
    })),
  }
}

function duplicateProtocolKinds(protocols: FormProtocol[]) {
  const counts = new Map<ProtocolKind, number>()
  for (const item of protocols) {
    counts.set(item.protocol, (counts.get(item.protocol) ?? 0) + 1)
  }
  return new Set([...counts.entries()].filter(([, count]) => count > 1).map(([protocol]) => protocol))
}

function SwitchButton({ checked, onChange, disabled = false }: { checked: boolean; onChange: (checked: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative h-6 w-11 rounded-full transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-60',
        checked ? 'bg-[var(--accent)]' : 'bg-[var(--line-strong)]'
      )}
    >
      <span className={cn('absolute top-1 h-4 w-4 rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,0.18)] transition-all duration-200', checked ? 'right-1' : 'left-1')} />
    </button>
  )
}

export function ChannelsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const [viewMode, setViewMode] = useState<ViewMode>('cards')
  const [search, setSearch] = useState('')
  const [detailTarget, setDetailTarget] = useState<SiteRow | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Site | null>(null)
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [fetchingProtocolIndex, setFetchingProtocolIndex] = useState<number | null>(null)
  const [advancedProtocolIndex, setAdvancedProtocolIndex] = useState<number | null>(null)
  const [modelPickerProtocolIndex, setModelPickerProtocolIndex] = useState<number | null>(null)
  const [availableModels, setAvailableModels] = useState<PickerModelItem[]>([])
  const [pickerSelectedModelKeys, setPickerSelectedModelKeys] = useState<string[]>([])
  const [formSnapshot, setFormSnapshot] = useState('')

  const { data: sites, isLoading } = useQuery({ queryKey: ['sites'], queryFn: () => apiRequest<Site[]>('/admin/sites') })
  const { data: requestLogs } = useQuery({ queryKey: ['request-logs'], queryFn: () => apiRequest<RequestLogItem[]>('/admin/request-logs') })

  const siteStats = useMemo(() => buildSiteStats(requestLogs, sites), [requestLogs, sites])
  const visibleSites = useMemo<SiteRow[]>(() => {
    const keyword = search.trim().toLowerCase()
    const rows = (sites ?? []).map((site) => ({
      ...site,
      subtitle: siteSubtitle(site),
      protocol_count: site.protocols.length,
      credential_count: site.credentials.length,
      model_count: siteModelCount(site),
      endpoint_summary: siteEndpointSummary(site),
    }))
    if (!keyword) return rows
    return rows.filter((site) => {
      const stack = [site.name, site.subtitle, site.endpoint_summary, ...site.protocols.flatMap((item) => item.models.map((model) => model.model_name))].join(' ').toLowerCase()
      return stack.includes(keyword)
    })
  }, [sites, search])
  const currentSnapshot = useMemo(() => JSON.stringify(toPayload(form)), [form])
  const hasUnsavedChanges = dialogOpen && currentSnapshot !== formSnapshot

  useEffect(() => {
    if (!dialogOpen) return
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [dialogOpen, hasUnsavedChanges])

  async function invalidateChannelData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['sites'] }),
      queryClient.invalidateQueries({ queryKey: ['request-logs'] }),
      queryClient.invalidateQueries({ queryKey: ['group-candidates'] }),
    ])
  }

  function openCreate() {
    setEditingSiteId(null)
    const nextForm = emptyForm()
    setForm(nextForm)
    setFormSnapshot(JSON.stringify(toPayload(nextForm)))
    setError('')
    setDetailTarget(null)
    setDialogOpen(true)
  }

  function openEdit(site: Site) {
    setEditingSiteId(site.id)
    const nextForm = toForm(site)
    setForm(nextForm)
    setFormSnapshot(JSON.stringify(toPayload(nextForm)))
    setError('')
    setDetailTarget(null)
    setDialogOpen(true)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const duplicatedProtocols = duplicateProtocolKinds(form.protocols)
    if (duplicatedProtocols.size) {
      setError(locale === 'zh-CN' ? '同一个渠道内不允许重复协议' : 'Duplicate protocols are not allowed in one channel')
      return
    }
    try {
      await apiRequest<Site>(editingSiteId ? `/admin/sites/${editingSiteId}` : '/admin/sites', {
        method: editingSiteId ? 'PUT' : 'POST',
        body: JSON.stringify(toPayload(form)),
      })
      setDialogOpen(false)
      setEditingSiteId(null)
      const nextForm = emptyForm()
      setForm(nextForm)
      setFormSnapshot(JSON.stringify(toPayload(nextForm)))
      await invalidateChannelData()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存渠道失败' : 'Failed to save channel'))
    }
  }

  async function removeSite(site: Site) {
    setBusyId(site.id)
    setError('')
    try {
      await apiRequest<void>(`/admin/sites/${site.id}`, { method: 'DELETE' })
      setDeleteTarget(null)
      setDetailTarget(null)
      await invalidateChannelData()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除渠道失败' : 'Failed to delete channel'))
    } finally {
      setBusyId(null)
    }
  }

  async function toggleSiteEnabled(site: Site, enabled: boolean) {
    setBusyId(site.id)
    setError('')
    try {
      await apiRequest<Site>(`/admin/sites/${site.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: site.name,
          base_url: site.base_url,
          credentials: site.credentials.map((item) => ({ id: item.id, name: item.name, api_key: item.api_key, enabled: item.enabled })),
          protocols: site.protocols.map((item) => ({
            id: item.id,
            protocol: item.protocol,
            enabled,
            headers: item.headers,
            channel_proxy: item.channel_proxy,
            param_override: item.param_override,
            match_regex: item.match_regex,
            bindings: item.bindings.map((binding) => ({ credential_id: binding.credential_id, enabled: binding.enabled })),
            models: item.models.map((model) => ({ id: model.id, credential_id: model.credential_id, model_name: model.model_name, enabled: model.enabled })),
          })),
        }),
      })
      if (detailTarget?.id === site.id) {
        setDetailTarget((current) => current ? { ...current, protocols: current.protocols.map((item) => ({ ...item, enabled })) } : current)
      }
      await invalidateChannelData()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '更新渠道状态失败' : 'Failed to update channel status'))
    } finally {
      setBusyId(null)
    }
  }

  function updateCredential(index: number, patch: Partial<FormCredential>) {
    setForm((current) => ({ ...current, credentials: current.credentials.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) }))
  }

  function removeCredential(index: number) {
    setForm((current) => {
      if (current.credentials.length <= 1) {
        return current
      }
      const target = current.credentials[index]
      if (!target) {
        return current
      }
      return {
        ...current,
        credentials: current.credentials.filter((_, itemIndex) => itemIndex !== index),
        protocols: current.protocols.map((protocol) => ({
          ...protocol,
          bindings: protocol.bindings.filter((binding) => binding.credential_id !== target.id),
          models: protocol.models.filter((model) => model.credential_id !== target.id),
          model_filter_credential_id: protocol.model_filter_credential_id === target.id ? null : protocol.model_filter_credential_id,
        })),
      }
    })
  }

  function updateProtocol(index: number, patch: Partial<FormProtocol>) {
    setForm((current) => ({ ...current, protocols: current.protocols.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) }))
  }

  function updateProtocolHeader(protocolIndex: number, headerIndex: number, patch: Partial<HeaderItem>) {
    setForm((current) => ({
      ...current,
      protocols: current.protocols.map((item, itemIndex) => itemIndex !== protocolIndex ? item : { ...item, headers: item.headers.map((header, currentHeaderIndex) => currentHeaderIndex === headerIndex ? { ...header, ...patch } : header) }),
    }))
  }

  function updateProtocolModel(protocolIndex: number, modelIndex: number, patch: Partial<SiteModelInput>) {
    setForm((current) => ({
      ...current,
      protocols: current.protocols.map((item, itemIndex) => itemIndex !== protocolIndex ? item : { ...item, models: item.models.map((model, currentModelIndex) => currentModelIndex === modelIndex ? { ...model, ...patch } : model) }),
    }))
  }

  function togglePickerModel(key: string) {
    setPickerSelectedModelKeys((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key])
  }

  async function fetchProtocolModels(protocolIndex: number) {
    const protocol = form.protocols[protocolIndex]
    if (!protocol) return
    const activeCredentials = form.credentials.filter((item, index) => item.enabled && item.api_key.trim()).map((item, index) => ({ ...item, display_name: credentialLabel(item, index, locale) }))
    const selectedCredentialId = activeCredentials.some((item) => item.id === protocol.model_filter_credential_id)
      ? protocol.model_filter_credential_id || ''
      : activeCredentials[0]?.id || ''
    setFetchingProtocolIndex(protocolIndex)
    setError('')
    try {
      const payload: SiteModelFetchPayload = {
        protocol: protocol.protocol,
        base_url: safeText(form.base_url).trim(),
        headers: Object.fromEntries(protocol.headers.map((entry) => [entry.key.trim(), entry.value] as const).filter(([key]) => key)),
        channel_proxy: protocol.channel_proxy.trim(),
        match_regex: safeText(protocol.match_regex).trim(),
        credentials: form.credentials.map((item, index) => ({ id: item.id, name: item.name.trim() || fallbackCredentialName(index), api_key: item.api_key.trim(), enabled: item.enabled })).filter((item) => item.api_key),
        bindings: selectedCredentialId
          ? [{ credential_id: selectedCredentialId, enabled: true }]
          : form.credentials.filter((item) => item.enabled && item.api_key.trim()).map((item) => ({ credential_id: item.id, enabled: true })),
      }
      const models = await apiRequest<SiteModelFetchItem[]>('/admin/site-model-discoveries', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      const nextAvailableModels = models.map((item) => ({ credential_id: item.credential_id, model_name: item.model_name }))
      const existingKeys = new Set(protocol.models.map((item) => `${item.credential_id}:${item.model_name}`))
      setAvailableModels(nextAvailableModels)
      setPickerSelectedModelKeys(nextAvailableModels.map((item) => `${item.credential_id}:${item.model_name}`).filter((key) => !existingKeys.has(key)))
      setModelPickerProtocolIndex(protocolIndex)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '刷新模型失败' : 'Failed to refresh models'))
    } finally {
      setFetchingProtocolIndex(null)
    }
  }

  function confirmModelSelection() {
    if (modelPickerProtocolIndex === null) return
    const selectedModels = availableModels.filter((item) => pickerSelectedModelKeys.includes(`${item.credential_id}:${item.model_name}`))
    setForm((current) => ({
      ...current,
      protocols: current.protocols.map((item, itemIndex) => {
        if (itemIndex !== modelPickerProtocolIndex) return item
        const merged = [...item.models]
        const existing = new Set(item.models.map((model) => `${model.credential_id}:${model.model_name}`))
        for (const model of selectedModels) {
          const key = `${model.credential_id}:${model.model_name}`
          if (existing.has(key)) continue
          existing.add(key)
          merged.push({ id: null, credential_id: model.credential_id, model_name: model.model_name, enabled: true })
        }
        return { ...item, models: merged, expanded: true }
      }),
    }))
    setModelPickerProtocolIndex(null)
    setAvailableModels([])
    setPickerSelectedModelKeys([])
  }

  const detailStats = detailTarget ? buildDetailStats(detailTarget, siteStats.get(detailTarget.id)) : null

  return (
    <section className="space-y-4">
      {typeof document !== 'undefined' && document.getElementById('header-portal') ? createPortal(
        <div className="flex flex-1 items-center justify-end gap-2">
          <div className="flex h-9 w-full max-w-sm items-center rounded-lg border border-[var(--line)] bg-[var(--panel-strong)] px-3 shadow-sm transition-colors focus-within:border-[var(--accent)]">
            <Search size={15} className="text-[var(--muted)]" />
            <input className="ml-2 h-full min-w-0 flex-1 bg-transparent text-[13px] outline-none" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索渠道 / 协议 / 模型' : 'Search channels, models...'} />
            {search ? <button type="button" className="text-[var(--muted)] hover:text-[var(--text)]" onClick={() => setSearch('')}><X size={14} /></button> : null}
          </div>
          <SegmentedControl value={viewMode} onValueChange={(value) => setViewMode(value as ViewMode)} options={[{ value: 'cards', label: locale === 'zh-CN' ? '卡片' : 'Cards' }, { value: 'list', label: locale === 'zh-CN' ? '列表' : 'List' }]} />
          <button type="button" onClick={openCreate} className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)] text-white shadow-sm transition-colors hover:opacity-90" title={locale === 'zh-CN' ? '新建渠道' : 'New channel'}>
            <Plus size={18} />
          </button>
        </div>,
        document.getElementById('header-portal')!
      ) : null}

      <div className="grid gap-4 mt-2">
        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载渠道...' : 'Loading channels...'}</p> : null}
      </div>

      {viewMode === 'cards' ? (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {visibleSites.map((site) => {
            const stats = siteStats.get(site.id)
            return (
              <article key={site.id} className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)] transition-colors hover:bg-[var(--panel-soft)]">
                <div className="flex items-start justify-between gap-3">
                  <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setDetailTarget(site)}>
                    <div className="truncate text-[17px] font-semibold text-[var(--text)]">{site.name}</div>
                  </button>
                  <div className="flex items-center gap-2">
                    <SwitchButton checked={isSiteEnabled(site)} disabled={busyId === site.id} onChange={(checked) => void toggleSiteEnabled(site, checked)} />
                    <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--text)]" onClick={() => openEdit(site)}><Pencil size={15} /></button>
                    <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--danger)] transition hover:bg-[rgba(217,111,93,0.08)]" onClick={() => setDeleteTarget(site)}><Trash2 size={15} /></button>
                  </div>
                </div>

                <button type="button" className="mt-4 grid w-full gap-3 text-left" onClick={() => setDetailTarget(site)}>
                  <div className="flex items-center justify-between rounded-[22px] border border-[var(--line)] bg-[var(--panel)] p-3">
                    <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(37,99,235,0.12)] text-[var(--accent)]"><Activity className="h-4 w-4" /></span><span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '请求数' : 'Requests'}</span></div>
                    <strong className="text-base text-[var(--text)]">{stats?.requestCount ?? 0}</strong>
                  </div>
                  <div className="flex items-center justify-between rounded-[22px] border border-[var(--line)] bg-[var(--panel)] p-3">
                    <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(37,99,235,0.12)] text-[var(--accent)]"><Waypoints className="h-4 w-4" /></span><span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '协议 / 模型' : 'Protocols / Models'}</span></div>
                    <strong className="text-base text-[var(--text)]">{site.protocol_count} / {site.model_count}</strong>
                  </div>
                </button>
              </article>
            )
          })}
        </div>
      ) : (
        <div className="overflow-hidden rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] shadow-[var(--shadow-sm)]">
          <div className="grid grid-cols-[minmax(0,1.1fr)_1fr_110px_120px_110px] gap-4 border-b border-[var(--line)] px-5 py-3 text-xs font-semibold text-[var(--muted)]">
            <span>{locale === 'zh-CN' ? '渠道' : 'Channel'}</span>
            <span>{locale === 'zh-CN' ? '概览' : 'Overview'}</span>
            <span>{locale === 'zh-CN' ? '请求数' : 'Requests'}</span>
            <span>{locale === 'zh-CN' ? '协议 / 模型' : 'Protocols / Models'}</span>
            <span>{locale === 'zh-CN' ? '操作' : 'Actions'}</span>
          </div>
          <div className="divide-y divide-[var(--line)]">
            {visibleSites.map((site) => {
              const stats = siteStats.get(site.id)
              return (
                <div key={site.id} className="grid grid-cols-[minmax(0,1.1fr)_1fr_110px_120px_110px] gap-4 px-5 py-4 text-sm text-[var(--text)]">
                  <button type="button" className="min-w-0 text-left" onClick={() => setDetailTarget(site)}>
                    <div className="truncate font-semibold">{site.name}</div>
                  </button>
                  <button type="button" className="min-w-0 text-left" onClick={() => setDetailTarget(site)}>
                    <div className="truncate text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '渠道概览' : 'Channel overview'}</div>
                    <div className="mt-1 truncate">{locale === 'zh-CN' ? `${site.protocol_count} 个协议，${site.model_count} 个模型` : `${site.protocol_count} protocols, ${site.model_count} models`}</div>
                  </button>
                  <div className="flex items-center text-[var(--muted)]">{stats?.requestCount ?? 0}</div>
                  <div className="flex items-center text-[var(--muted)]">{site.protocol_count} / {site.model_count}</div>
                  <div className="flex items-center justify-end gap-2">
                    <SwitchButton checked={isSiteEnabled(site)} disabled={busyId === site.id} onChange={(checked) => void toggleSiteEnabled(site, checked)} />
                    <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--text)]" onClick={() => openEdit(site)}><Pencil size={15} /></button>
                    <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--danger)] transition hover:bg-[rgba(217,111,93,0.08)]" onClick={() => setDeleteTarget(site)}><Trash2 size={15} /></button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <Dialog.Root open={Boolean(detailTarget)} onOpenChange={(open) => { if (!open) setDetailTarget(null) }}>
        {detailTarget && detailStats ? (
          <AppDialogContent className="max-w-4xl" title={locale === 'zh-CN' ? '渠道详情' : 'Channel detail'}>
            <div className="space-y-6">
              <div className="grid gap-3 sm:grid-cols-2">
                <MetricCard icon={<Activity className="h-4 w-4 text-[var(--accent)]" />} label={locale === 'zh-CN' ? '总请求' : 'Requests'} value={String(detailStats.requestCount)} tone="accent" />
                <MetricCard icon={<Server className="h-4 w-4 text-[var(--accent)]" />} label={locale === 'zh-CN' ? '模型数' : 'Models'} value={String(detailStats.modelCount)} />
                <MetricCard icon={<Waypoints className="h-4 w-4 text-[var(--accent)]" />} label={locale === 'zh-CN' ? '协议数' : 'Protocols'} value={String(detailStats.protocolCount)} />
                <MetricCard icon={<KeyRound className="h-4 w-4 text-[var(--accent)]" />} label={locale === 'zh-CN' ? '密钥数' : 'Keys'} value={String(detailStats.credentialCount)} />
                <MetricCard icon={<Activity className="h-4 w-4 text-[var(--accent)]" />} label={locale === 'zh-CN' ? '成功' : 'Success'} value={String(detailStats.successCount)} />
                <MetricCard icon={<Activity className="h-4 w-4 text-[var(--danger)]" />} label={locale === 'zh-CN' ? '失败' : 'Failed'} value={String(detailStats.failedCount)} tone="danger" />
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <button className="h-12 rounded-[18px] bg-[var(--accent)] text-sm font-medium text-white" type="button" onClick={() => openEdit(detailTarget)}>{locale === 'zh-CN' ? '编辑渠道' : 'Edit channel'}</button>
                <button className="h-12 rounded-[18px] bg-[var(--danger)] text-sm font-medium text-white" type="button" onClick={() => setDeleteTarget(detailTarget)}>{locale === 'zh-CN' ? '删除渠道' : 'Delete channel'}</button>
              </div>
            </div>
          </AppDialogContent>
        ) : null}
      </Dialog.Root>

      <Dialog.Root open={dialogOpen} onOpenChange={(open) => {
        if (!open && hasUnsavedChanges) {
          const confirmed = window.confirm(locale === 'zh-CN' ? '当前有未保存修改，确定关闭吗？' : 'You have unsaved changes. Close anyway?')
          if (!confirmed) return
        }
        setDialogOpen(open)
      }}>
        <AppDialogContent className="max-w-4xl" title={editingSiteId ? (locale === 'zh-CN' ? '编辑渠道' : 'Edit channel') : (locale === 'zh-CN' ? '新建渠道' : 'Create channel')}>
          <form className="grid gap-6" onSubmit={submit}>
            <div className="grid gap-5">
              <section className="grid gap-4">
                <div className="text-lg font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '基本信息' : 'Channel and keys'}</div>
                <div className="grid gap-4">
                  <div className="grid gap-4 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                    <label className="grid gap-2">
                      <span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '渠道名称' : 'Channel name'}</span>
                      <input className={inputClassName()} value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
                    </label>
                    <label className="grid gap-2">
                      <span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '请求地址' : 'Base URL'}</span>
                      <input className={inputClassName()} value={form.base_url} onChange={(event) => setForm((current) => ({ ...current, base_url: event.target.value }))} placeholder="https://api.example.com" />
                    </label>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '密钥' : 'API Keys'}</div>
                      <button type="button" onClick={() => setForm((current) => ({ ...current, credentials: [...current.credentials, { id: createCredentialId(), name: '', api_key: '', enabled: true }] }))} className="text-sm text-[var(--accent)]">+ {locale === 'zh-CN' ? '添加' : 'Add'}</button>
                    </div>
                    {form.credentials.map((credential, index) => (
                      <div key={credential.id} className="grid gap-3 md:grid-cols-[1.4fr_0.7fr_auto_auto] md:items-center">
                        <input className={inputClassName()} value={credential.api_key} onChange={(event) => updateCredential(index, { api_key: event.target.value })} placeholder="sk-..." />
                        <input className={inputClassName()} value={credential.name} onChange={(event) => updateCredential(index, { name: event.target.value })} placeholder={locale === 'zh-CN' ? '备注' : 'Remark'} />
                        <SwitchButton checked={credential.enabled} onChange={(checked) => updateCredential(index, { enabled: checked })} />
                        <button type="button" className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--line)] text-[var(--muted)]" onClick={() => removeCredential(index)}><X size={16} /></button>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              <section className="grid gap-4">
                <div className="text-lg font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '协议列表' : 'Protocol configs'}</div>
                <div className="space-y-4">
                  {form.protocols.map((protocol, protocolIndex) => {
                    const duplicatedProtocols = duplicateProtocolKinds(form.protocols)
                    const activeCredentialIds = new Set(form.credentials.filter((item) => item.enabled && item.api_key.trim()).map((item) => item.id))
                    const credentialOptions = form.credentials
                      .map((item, index) => ({ ...item, display_name: credentialLabel(item, index, locale) }))
                      .filter((item) => activeCredentialIds.has(item.id))
                    const selectedCredentialId = credentialOptions.some((item) => item.id === protocol.model_filter_credential_id)
                      ? protocol.model_filter_credential_id || ''
                      : credentialOptions[0]?.id || ''
                    const visibleModels = protocol.models
                      .map((model, modelIndex) => ({ model, modelIndex }))
                      .filter(({ model }) => !selectedCredentialId || model.credential_id === selectedCredentialId)

                    return (
                      <div key={protocol.id || protocolIndex} className="py-2">
                        <div className="flex flex-col gap-3">
                          <div className="grid gap-3 lg:grid-cols-[180px_180px_auto_auto_auto_1fr] lg:items-center">
                            <select className={inputClassName()} value={protocol.protocol} onChange={(event) => updateProtocol(protocolIndex, { protocol: event.target.value as ProtocolKind })}>
                              {protocolOptions.map((option) => {
                                const takenByOtherRow = form.protocols.some((item, itemIndex) => itemIndex !== protocolIndex && item.protocol === option.value)
                                return <option key={option.value} value={option.value} disabled={takenByOtherRow}>{option.label}</option>
                              })}
                            </select>
                            <select className={inputClassName()} value={selectedCredentialId} onChange={(event) => updateProtocol(protocolIndex, { model_filter_credential_id: event.target.value || null })}>
                              {credentialOptions.length ? credentialOptions.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>) : <option value="">{locale === 'zh-CN' ? '无可用密钥' : 'No key'}</option>}
                            </select>
                            <SwitchButton checked={protocol.enabled} onChange={(checked) => updateProtocol(protocolIndex, { enabled: checked })} />
                            <button type="button" className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--line)] text-[var(--muted)]" onClick={() => setAdvancedProtocolIndex(protocolIndex)}><Ellipsis size={16} /></button>
                            <button type="button" className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--line)] text-[var(--danger)]" onClick={() => setForm((current) => ({ ...current, protocols: current.protocols.length > 1 ? current.protocols.filter((_, currentIndex) => currentIndex !== protocolIndex) : current.protocols }))}><X size={16} /></button>
                            <div className="flex items-center justify-end">
                              <button type="button" onClick={() => updateProtocol(protocolIndex, { expanded: !protocol.expanded })} className="inline-flex items-center gap-2 text-sm text-[var(--muted)] transition hover:text-[var(--text)]">
                                <span>{locale === 'zh-CN' ? '模型列表' : 'Models'}</span>
                                <ChevronDown size={16} className={cn('transition-transform', protocol.expanded ? 'rotate-180' : '')} />
                              </button>
                            </div>
                          </div>

                          {duplicatedProtocols.has(protocol.protocol) ? <div className="text-sm text-[var(--danger)]">{locale === 'zh-CN' ? '协议类型重复' : 'Duplicate protocol'}</div> : null}

                          {protocol.expanded ? (
                            <div className="grid gap-3 border-t border-[var(--line)] pt-3">
                              <div className="grid gap-2 xl:grid-cols-[minmax(0,1fr)_auto_auto] xl:items-center">
                                <input
                                  className="h-10 min-w-[180px] rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]"
                                  value={protocol.match_regex}
                                  onChange={(event) => updateProtocol(protocolIndex, { match_regex: event.target.value })}
                                  placeholder={locale === 'zh-CN' ? '匹配规则' : 'Match regex'}
                                />
                                <button type="button" onClick={() => updateProtocol(protocolIndex, { models: [] })} disabled={!visibleModels.length} className="h-10 rounded-xl border border-[rgba(217,111,93,0.28)] px-3 text-sm text-[var(--danger)] disabled:cursor-not-allowed disabled:opacity-60">{locale === 'zh-CN' ? '删除所有模型' : 'Remove all'}</button>
                                <button type="button" onClick={() => void fetchProtocolModels(protocolIndex)} disabled={fetchingProtocolIndex === protocolIndex || !safeText(form.base_url).trim() || !activeCredentialIds.size} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[var(--accent)] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60">
                                  <RefreshCcw size={14} className={fetchingProtocolIndex === protocolIndex ? 'animate-spin' : ''} />
                                  {locale === 'zh-CN' ? '刷新模型' : 'Refresh models'}
                                </button>
                              </div>

                              <div className="flex flex-wrap items-center gap-2.5">
                                {visibleModels.length ? (
                                  <>
                                  {visibleModels.map(({ model, modelIndex }) => (
                                    <button key={model.id || `${model.credential_id}-${model.model_name}-${modelIndex}`} type="button" className={modelBadgeClassName(model.enabled)} onClick={() => updateProtocol(protocolIndex, { models: protocol.models.filter((_, currentIndex) => currentIndex !== modelIndex) })}>
                                      <span>{model.model_name}</span>
                                      <X size={14} />
                                    </button>
                                  ))}
                                  </>
                                ) : (
                                  <div className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '当前没有模型' : 'No models selected'}</div>
                                )}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}

                  <button type="button" className="inline-flex h-10 items-center justify-center gap-2 text-sm font-medium text-[var(--accent)]" onClick={() => setForm((current) => ({ ...current, protocols: [...current.protocols, emptyProtocol()] }))}>
                    <Plus size={16} />
                    {locale === 'zh-CN' ? '增加一个协议' : 'Add protocol config'}
                  </button>
                </div>
              </section>
            </div>

            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-3">
              <button type="button" className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-5 py-2.5 text-sm text-[var(--text)]" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button type="submit" className="rounded-xl bg-[var(--accent)] px-5 py-2.5 text-sm font-medium text-white">{editingSiteId ? (locale === 'zh-CN' ? '保存渠道' : 'Save channel') : (locale === 'zh-CN' ? '创建渠道' : 'Create channel')}</button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={advancedProtocolIndex !== null} onOpenChange={(open) => { if (!open) setAdvancedProtocolIndex(null) }}>
        {advancedProtocolIndex !== null && form.protocols[advancedProtocolIndex] ? (
          <AppDialogContent className="max-w-3xl" title={locale === 'zh-CN' ? '更多设置' : 'More settings'}>
            <div className="grid gap-4">
              <label className="grid gap-2">
                <span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '代理地址' : 'Proxy'}</span>
                <input className={inputClassName()} value={form.protocols[advancedProtocolIndex].channel_proxy} onChange={(event) => updateProtocol(advancedProtocolIndex, { channel_proxy: event.target.value })} placeholder="http://127.0.0.1:7890" />
              </label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '请求头' : 'Headers'}</div>
                  <button type="button" className="text-sm text-[var(--accent)]" onClick={() => updateProtocol(advancedProtocolIndex, { headers: [...form.protocols[advancedProtocolIndex].headers, { key: '', value: '' }] })}>+ {locale === 'zh-CN' ? '添加' : 'Add'}</button>
                </div>
                {form.protocols[advancedProtocolIndex].headers.map((header, headerIndex) => (
                  <div key={headerIndex} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                    <input className={inputClassName()} value={header.key} onChange={(event) => updateProtocolHeader(advancedProtocolIndex, headerIndex, { key: event.target.value })} placeholder={locale === 'zh-CN' ? '请求头名称' : 'Header-Key'} />
                    <input className={inputClassName()} value={header.value} onChange={(event) => updateProtocolHeader(advancedProtocolIndex, headerIndex, { value: event.target.value })} placeholder={locale === 'zh-CN' ? '请求头值' : 'Header-Value'} />
                    <button type="button" className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--line)] text-[var(--muted)]" onClick={() => updateProtocol(advancedProtocolIndex, { headers: form.protocols[advancedProtocolIndex].headers.length > 1 ? form.protocols[advancedProtocolIndex].headers.filter((_, currentIndex) => currentIndex !== headerIndex) : form.protocols[advancedProtocolIndex].headers })}><X size={16} /></button>
                  </div>
                ))}
              </div>
              <label className="grid gap-2">
                <span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '参数覆盖' : 'Param Override'}</span>
                <textarea className={textareaClassName()} value={form.protocols[advancedProtocolIndex].param_override} onChange={(event) => updateProtocol(advancedProtocolIndex, { param_override: event.target.value })} />
              </label>
            </div>
          </AppDialogContent>
        ) : null}
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除渠道' : 'Delete channel'} description={locale === 'zh-CN' ? '删除后该渠道下的协议、模型和模型组成员会一起移除。' : 'Protocol configs, models, and group members under this channel will be removed together.'}>
          <div className="grid gap-5">
            <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel)] p-4">
              <strong className="text-[var(--text)]">{deleteTarget?.name}</strong>
              <p className="mt-2 text-sm text-[var(--muted)]">{deleteTarget ? siteSubtitle(deleteTarget) : ''}</p>
            </div>
            <div className="flex justify-end gap-3">
              <button type="button" className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" onClick={() => setDeleteTarget(null)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button type="button" className="rounded-xl bg-[var(--danger)] px-4 py-2.5 text-sm font-medium text-white" onClick={() => deleteTarget && void removeSite(deleteTarget)} disabled={busyId === deleteTarget?.id}>{busyId === deleteTarget?.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '确认删除' : 'Delete')}</button>
            </div>
          </div>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={modelPickerProtocolIndex !== null} onOpenChange={(open) => {
        if (!open) {
          setModelPickerProtocolIndex(null)
          setAvailableModels([])
          setPickerSelectedModelKeys([])
        }
      }}>
        {modelPickerProtocolIndex !== null ? (
          <AppDialogContent className="max-w-3xl" title={locale === 'zh-CN' ? '选择模型' : 'Select models'}>
            <div className="grid gap-4">
              <div className="max-h-[420px] overflow-y-auto p-1">
                <div className="flex flex-wrap gap-2.5">
                  {availableModels.length ? availableModels.map((model) => {
                    const key = `${model.credential_id}:${model.model_name}`
                    const checked = pickerSelectedModelKeys.includes(key)
                    return (
                      <button key={key} type="button" onClick={() => togglePickerModel(key)} className={cn(modelBadgeClassName(checked), checked ? 'border-[var(--accent)] text-[var(--accent)]' : '')}>
                        <span className="truncate">{model.model_name}</span>
                        <span className="text-xs">{checked ? '✓' : '+'}</span>
                      </button>
                    )
                  }) : <div className="px-3 py-6 text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '未获取到可选模型' : 'No models fetched.'}</div>}
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <button type="button" className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" onClick={() => {
                  setModelPickerProtocolIndex(null)
                  setAvailableModels([])
                  setPickerSelectedModelKeys([])
                }}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
                <button type="button" className="rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white" onClick={confirmModelSelection}>{locale === 'zh-CN' ? '加入模型' : 'Add models'}</button>
              </div>
            </div>
          </AppDialogContent>
        ) : null}
      </Dialog.Root>
    </section>
  )
}

