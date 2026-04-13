"use client"

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, ChevronDown, Ellipsis, KeyRound, Pencil, Plus, RefreshCcw, Server, Trash2, Waypoints, X } from 'lucide-react'
import {
  ApiError,
  ProtocolKind,
  RequestLogItem,
  Site,
  SiteBaseUrlInput,
  SiteCredentialInput,
  SiteModelFetchItem,
  SiteModelFetchPayload,
  SitePayload,
  SiteProtocolCredentialBindingInput,
  SiteModelInput,
  apiRequest,
} from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemFooter,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from '@/components/ui/item'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ToolbarSearchInput } from '@/components/ui/toolbar-search-input'

const protocolOptions: Array<{ value: ProtocolKind; label: string }> = [
  { value: 'openai_chat', label: 'OpenAI Chat' },
  { value: 'openai_responses', label: 'OpenAI Responses' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
]

type HeaderItem = { key: string; value: string }
type FormCredential = Omit<SiteCredentialInput, 'id'> & { id: string }
type FormBaseUrl = Omit<SiteBaseUrlInput, 'id'> & { id: string }

function createCredentialId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `credential-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function createBaseUrlId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `baseurl-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

type FormProtocol = {
  id?: string | null
  protocol: ProtocolKind
  enabled: boolean
  headers: HeaderItem[]
  channel_proxy: string
  param_override: string
  match_regex: string
  manual_model_name: string
  base_url_id: string
  bindings: SiteProtocolCredentialBindingInput[]
  models: SiteModelInput[]
  expanded: boolean
  model_filter_credential_id?: string | null
}

type FormState = {
  name: string
  base_urls: FormBaseUrl[]
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
  manual_model_name: '',
  base_url_id: '',
  bindings: [],
  models: [],
  expanded: true,
  model_filter_credential_id: null,
})

const emptyForm = (): FormState => ({
  name: '',
  base_urls: [{ id: createBaseUrlId(), url: '', name: '', enabled: true }],
  credentials: [{ id: createCredentialId(), name: '', api_key: '', enabled: true }],
  protocols: [emptyProtocol()],
})

function protocolLabel(protocol: ProtocolKind) {
  return protocolOptions.find((item) => item.value === protocol)?.label ?? protocol
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
    ? 'inline-flex h-8 items-center gap-2 rounded-full border bg-background px-3 text-sm font-medium text-foreground transition hover:bg-muted'
    : 'inline-flex h-8 items-center gap-2 rounded-full border bg-muted/40 px-3 text-sm font-medium text-muted-foreground'
}

function selectClassName() {
  return 'w-full [&_select]:border-border [&_select]:bg-background [&_select]:text-sm [&_select]:text-foreground'
}

function siteSubtitle(site: Site) {
  return site.protocols.map((item) => protocolLabel(item.protocol)).join(' / ')
}

function siteEndpointSummary(site: Site) {
  const enabled = site.base_urls.filter((item) => item.enabled)
  if (enabled.length) return enabled[0].url
  return site.base_urls[0]?.url || ''
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
    ? 'text-primary'
    : tone === 'danger'
      ? 'text-destructive'
      : 'text-foreground'

  return (
    <div className="rounded-md border bg-muted/30 px-4 py-4">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">{icon}{label}</div>
      <div className={cn('mt-4 text-base font-semibold leading-none', valueClassName)}>{value}</div>
    </div>
  )
}

function ChannelMetric({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="inline-flex min-h-8 items-center gap-2 text-xs text-muted-foreground">
      <span className="inline-flex size-4.5 items-center justify-center">{icon}</span>
      <span className="truncate">{label} {value}</span>
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
    base_urls: site.base_urls.length
      ? site.base_urls.map((item) => ({ id: item.id, url: item.url, name: item.name, enabled: item.enabled }))
      : [{ id: createBaseUrlId(), url: '', name: '', enabled: true }],
    credentials: site.credentials.map((item) => ({ id: item.id, name: isGeneratedCredentialName(item.name) ? '' : item.name, api_key: item.api_key, enabled: item.enabled })),
    protocols: site.protocols.map((item) => ({
      id: item.id,
      protocol: item.protocol,
      enabled: item.enabled,
      headers: Object.entries(item.headers).length ? Object.entries(item.headers).map(([key, value]) => ({ key, value })) : [{ key: '', value: '' }],
      channel_proxy: item.channel_proxy,
      param_override: item.param_override,
      match_regex: safeText(item.match_regex),
      manual_model_name: '',
      base_url_id: item.base_url_id,
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
    base_urls: form.base_urls
      .map((item) => ({ id: item.id, url: item.url.trim(), name: item.name.trim(), enabled: item.enabled }))
      .filter((item) => item.url),
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
      base_url_id: item.base_url_id,
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
  return <Switch checked={checked} disabled={disabled} onCheckedChange={onChange} />
}

export function ChannelsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
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
          base_urls: site.base_urls.map((item) => ({ id: item.id, url: item.url, name: item.name, enabled: item.enabled })),
          credentials: site.credentials.map((item) => ({ id: item.id, name: item.name, api_key: item.api_key, enabled: item.enabled })),
          protocols: site.protocols.map((item) => ({
            id: item.id,
            protocol: item.protocol,
            enabled,
            headers: item.headers,
            channel_proxy: item.channel_proxy,
            param_override: item.param_override,
            match_regex: item.match_regex,
            base_url_id: item.base_url_id,
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

  function addManualProtocolModel(protocolIndex: number, credentialId: string) {
    setForm((current) => ({
      ...current,
      protocols: current.protocols.map((item, itemIndex) => {
        if (itemIndex !== protocolIndex) return item
        const modelName = item.manual_model_name.trim()
        if (!credentialId || !modelName) return item
        const exists = item.models.some((model) => model.credential_id === credentialId && model.model_name === modelName)
        if (exists) {
          return { ...item, manual_model_name: '', expanded: true }
        }
        return {
          ...item,
          manual_model_name: '',
          expanded: true,
          models: [...item.models, { id: null, credential_id: credentialId, model_name: modelName, enabled: true }],
        }
      }),
    }))
  }

  function togglePickerModel(key: string) {
    setPickerSelectedModelKeys((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key])
  }

  function closeModelPicker() {
    setModelPickerProtocolIndex(null)
    setAvailableModels([])
    setPickerSelectedModelKeys([])
  }

  function applyModelSelection(selectedKeys: string[]) {
    if (modelPickerProtocolIndex === null) return
    const selectedModels = availableModels.filter((item) => selectedKeys.includes(`${item.credential_id}:${item.model_name}`))
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
    closeModelPicker()
  }

  async function fetchProtocolModels(protocolIndex: number) {
    const protocol = form.protocols[protocolIndex]
    if (!protocol) return
    const activeCredentials = form.credentials.filter((item) => item.enabled && item.api_key.trim()).map((item, index) => ({ ...item, display_name: credentialLabel(item, index, locale) }))
    const selectedCredentialId = activeCredentials.some((item) => item.id === protocol.model_filter_credential_id)
      ? protocol.model_filter_credential_id || ''
      : activeCredentials[0]?.id || ''
    setFetchingProtocolIndex(protocolIndex)
    setError('')
    try {
      const boundBaseUrl = protocol.base_url_id ? form.base_urls.find((item) => item.id === protocol.base_url_id) : undefined
      const activeBaseUrl = boundBaseUrl?.url || form.base_urls.find((item) => item.enabled && item.url.trim())?.url || form.base_urls[0]?.url || ''
      const payload: SiteModelFetchPayload = {
        protocol: protocol.protocol,
        base_url: safeText(activeBaseUrl).trim(),
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
      setAvailableModels(nextAvailableModels)
      setPickerSelectedModelKeys([])
      setModelPickerProtocolIndex(protocolIndex)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '刷新模型失败' : 'Failed to refresh models'))
    } finally {
      setFetchingProtocolIndex(null)
    }
  }

  function confirmModelSelection() {
    applyModelSelection(pickerSelectedModelKeys)
  }

  function confirmAllModelSelection() {
    applyModelSelection(availableModels.map((item) => `${item.credential_id}:${item.model_name}`))
  }

  const detailStats = detailTarget ? buildDetailStats(detailTarget, siteStats.get(detailTarget.id)) : null

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">{locale === 'zh-CN' ? '渠道' : 'Channels'}</h1>
        <div className="flex items-center gap-2">
          <ToolbarSearchInput
            value={search}
            onChange={setSearch}
            onClear={() => setSearch('')}
            placeholder={locale === 'zh-CN' ? '搜索渠道 / 协议 / 模型' : 'Search channels, models...'}
          />
          <Button type="button" onClick={openCreate} className="rounded-lg" size="icon-sm" title={locale === 'zh-CN' ? '新建渠道' : 'New channel'}>
            <Plus size={18} />
          </Button>
        </div>
      </div>

      <div className="grid gap-4 mt-2">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {isLoading ? <p className="text-sm text-muted-foreground">{locale === 'zh-CN' ? '正在加载渠道...' : 'Loading channels...'}</p> : null}
      </div>

      {visibleSites.length ? (
        <div className="rounded-xl border bg-card p-3">
          <ItemGroup className="gap-3">
            {visibleSites.map((site) => {
              const stats = siteStats.get(site.id)
              return (
                <Item key={site.id} variant="outline" className="gap-4 px-4 py-4">
                  <ItemMedia variant="icon" className="flex size-11 rounded-xl bg-primary/10 text-primary">
                    <Waypoints className="h-5 w-5" />
                  </ItemMedia>
                  <Button type="button" variant="ghost" className="h-auto min-w-0 flex-1 justify-start p-0 text-left hover:bg-transparent" onClick={() => setDetailTarget(site)}>
                    <ItemContent className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <ItemTitle className="truncate">{site.name}</ItemTitle>
                      </div>
                      <ItemDescription className="mt-1 truncate">{site.subtitle || site.endpoint_summary || (locale === 'zh-CN' ? '未配置协议' : 'No protocols')}</ItemDescription>
                      <ItemFooter className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
                        <ChannelMetric icon={<Activity size={14} />} label={locale === 'zh-CN' ? '请求数' : 'Requests'} value={String(stats?.requestCount ?? 0)} />
                        <ChannelMetric icon={<Waypoints size={14} />} label={locale === 'zh-CN' ? '协议' : 'Protocols'} value={String(site.protocol_count)} />
                        <ChannelMetric icon={<Server size={14} />} label={locale === 'zh-CN' ? '模型' : 'Models'} value={String(site.model_count)} />
                        <ChannelMetric icon={<KeyRound size={14} />} label={locale === 'zh-CN' ? '密钥' : 'Keys'} value={String(site.credential_count)} />
                      </ItemFooter>
                    </ItemContent>
                  </Button>
                  <ItemActions className="ml-auto self-start">
                    <SwitchButton checked={isSiteEnabled(site)} disabled={busyId === site.id} onChange={(checked) => void toggleSiteEnabled(site, checked)} />
                    <Button type="button" variant="ghost" size="icon-sm" className="text-muted-foreground" onClick={() => openEdit(site)}><Pencil size={15} /></Button>
                    <Button type="button" variant="ghost" size="icon-sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteTarget(site)}><Trash2 size={15} /></Button>
                  </ItemActions>
                </Item>
              )
            })}
          </ItemGroup>
        </div>
      ) : null}

      {!isLoading && !visibleSites.length ? (
        <div className="rounded-xl border border-dashed bg-card px-6 py-12 text-center text-sm text-muted-foreground">
          {search.trim()
            ? (locale === 'zh-CN' ? '没有匹配的渠道。' : 'No matching channels.')
            : (locale === 'zh-CN' ? '当前还没有渠道。' : 'No channels yet.')}
        </div>
      ) : null}

      <Dialog open={Boolean(detailTarget)} onOpenChange={(open) => { if (!open) setDetailTarget(null) }}>
        {detailTarget && detailStats ? (
          <AppDialogContent className="max-w-4xl" title={locale === 'zh-CN' ? '渠道详情' : 'Channel detail'}>
            <div className="flex flex-col gap-6">
              <div className="grid gap-3 sm:grid-cols-2">
                <MetricCard icon={<Activity className="h-4 w-4 text-primary" />} label={locale === 'zh-CN' ? '总请求' : 'Requests'} value={String(detailStats.requestCount)} tone="accent" />
                <MetricCard icon={<Server className="h-4 w-4 text-primary" />} label={locale === 'zh-CN' ? '模型数' : 'Models'} value={String(detailStats.modelCount)} />
                <MetricCard icon={<Waypoints className="h-4 w-4 text-primary" />} label={locale === 'zh-CN' ? '协议数' : 'Protocols'} value={String(detailStats.protocolCount)} />
                <MetricCard icon={<KeyRound className="h-4 w-4 text-primary" />} label={locale === 'zh-CN' ? '密钥数' : 'Keys'} value={String(detailStats.credentialCount)} />
                <MetricCard icon={<Activity className="h-4 w-4 text-primary" />} label={locale === 'zh-CN' ? '成功' : 'Success'} value={String(detailStats.successCount)} />
                <MetricCard icon={<Activity className="h-4 w-4 text-destructive" />} label={locale === 'zh-CN' ? '失败' : 'Failed'} value={String(detailStats.failedCount)} tone="danger" />
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <Button className="h-11" type="button" onClick={() => openEdit(detailTarget)}>{locale === 'zh-CN' ? '编辑渠道' : 'Edit channel'}</Button>
                <Button className="h-11" variant="destructive" type="button" onClick={() => setDeleteTarget(detailTarget)}>{locale === 'zh-CN' ? '删除渠道' : 'Delete channel'}</Button>
              </div>
            </div>
          </AppDialogContent>
        ) : null}
      </Dialog>

      <Dialog open={dialogOpen} onOpenChange={(open) => {
        if (!open && hasUnsavedChanges) {
          const confirmed = window.confirm(locale === 'zh-CN' ? '当前有未保存修改，确定关闭吗？' : 'You have unsaved changes. Close anyway?')
          if (!confirmed) return
        }
        setDialogOpen(open)
      }}>
        <AppDialogContent className="max-w-4xl" title={editingSiteId ? (locale === 'zh-CN' ? '编辑渠道' : 'Edit channel') : (locale === 'zh-CN' ? '新建渠道' : 'Create channel')}>
          <form className="grid gap-5" onSubmit={submit}>
            <div className="grid gap-4">
              <section className="grid gap-5">
                <div className="text-base font-semibold text-foreground">{locale === 'zh-CN' ? '基本信息' : 'Channel and keys'}</div>
                <FieldGroup className="gap-4">
                  <Field>
                    <FieldLabel htmlFor="channel-name">{locale === 'zh-CN' ? '渠道名称' : 'Channel name'}</FieldLabel>
                    <Input id="channel-name" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
                  </Field>

                  <div className="grid gap-4 xl:grid-cols-2">
                    <section className="grid gap-3">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="text-sm font-medium text-foreground">{locale === 'zh-CN' ? '请求地址' : 'Base URLs'}</div>
                        <Button type="button" variant="outline" size="sm" onClick={() => setForm((current) => ({ ...current, base_urls: [...current.base_urls, { id: createBaseUrlId(), url: '', name: '', enabled: true }] }))}>
                          <Plus data-icon="inline-start" />
                          {locale === 'zh-CN' ? '添加' : 'Add'}
                        </Button>
                      </div>
                      <FieldGroup className="gap-3">
                        {form.base_urls.map((baseUrl, index) => (
                          <div key={baseUrl.id} className="grid gap-3 border-b pb-3 last:border-b-0 last:pb-0 md:grid-cols-[minmax(0,1.65fr)_minmax(0,0.85fr)_32px_32px] md:items-end">
                            <FieldGroup className="gap-3 contents">
                              <Field>
                                <FieldLabel>{locale === 'zh-CN' ? '地址' : 'URL'}</FieldLabel>
                                <Input value={baseUrl.url} onChange={(event) => setForm((current) => ({ ...current, base_urls: current.base_urls.map((item, i) => i === index ? { ...item, url: event.target.value } : item) }))} placeholder="https://api.example.com" />
                              </Field>
                              <Field>
                                <FieldLabel>{locale === 'zh-CN' ? '备注' : 'Remark'}</FieldLabel>
                                <Input value={baseUrl.name} onChange={(event) => setForm((current) => ({ ...current, base_urls: current.base_urls.map((item, i) => i === index ? { ...item, name: event.target.value } : item) }))} placeholder={locale === 'zh-CN' ? '备注' : 'Remark'} />
                              </Field>
                              <div className="flex h-8 w-8 items-center justify-center">
                                <SwitchButton checked={baseUrl.enabled} onChange={(checked) => setForm((current) => ({ ...current, base_urls: current.base_urls.map((item, i) => i === index ? { ...item, enabled: checked } : item) }))} />
                              </div>
                              <Button type="button" variant="outline" size="icon" className="text-muted-foreground" onClick={() => setForm((current) => ({ ...current, base_urls: current.base_urls.length > 1 ? current.base_urls.filter((_, i) => i !== index) : current.base_urls }))} disabled={form.base_urls.length <= 1}><X size={16} /></Button>
                            </FieldGroup>
                          </div>
                        ))}
                      </FieldGroup>
                    </section>

                    <section className="grid gap-3">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="text-sm font-medium text-foreground">{locale === 'zh-CN' ? '密钥' : 'API Keys'}</div>
                        <Button type="button" variant="outline" size="sm" onClick={() => setForm((current) => ({ ...current, credentials: [...current.credentials, { id: createCredentialId(), name: '', api_key: '', enabled: true }] }))}>
                          <Plus data-icon="inline-start" />
                          {locale === 'zh-CN' ? '添加' : 'Add'}
                        </Button>
                      </div>
                      <FieldGroup className="gap-3">
                        {form.credentials.map((credential, index) => (
                          <div key={credential.id} className="grid gap-3 border-b pb-3 last:border-b-0 last:pb-0 md:grid-cols-[minmax(0,1.65fr)_minmax(0,0.85fr)_32px_32px] md:items-end">
                            <FieldGroup className="gap-3 contents">
                              <Field>
                                <FieldLabel>{locale === 'zh-CN' ? '密钥' : 'API key'}</FieldLabel>
                                <Input value={credential.api_key} onChange={(event) => updateCredential(index, { api_key: event.target.value })} placeholder="sk-..." />
                              </Field>
                              <Field>
                                <FieldLabel>{locale === 'zh-CN' ? '备注' : 'Remark'}</FieldLabel>
                                <Input value={credential.name} onChange={(event) => updateCredential(index, { name: event.target.value })} placeholder={locale === 'zh-CN' ? '备注' : 'Remark'} />
                              </Field>
                              <div className="flex h-8 w-8 items-center justify-center">
                                <SwitchButton checked={credential.enabled} onChange={(checked) => updateCredential(index, { enabled: checked })} />
                              </div>
                              <Button type="button" variant="outline" size="icon" className="text-muted-foreground" onClick={() => removeCredential(index)}><X size={16} /></Button>
                            </FieldGroup>
                          </div>
                        ))}
                      </FieldGroup>
                    </section>
                  </div>
                </FieldGroup>
              </section>

              <Separator />

              <section className="grid gap-4">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div className="text-base font-semibold text-foreground">{locale === 'zh-CN' ? '协议列表' : 'Protocol configs'}</div>
                  <Button type="button" variant="outline" className="justify-start border-dashed" onClick={() => setForm((current) => ({ ...current, protocols: [...current.protocols, emptyProtocol()] }))}>
                    <Plus data-icon="inline-start" />
                    {locale === 'zh-CN' ? '增加一个协议' : 'Add protocol config'}
                  </Button>
                </div>
                <div className="flex flex-col gap-3">
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
                      <div key={protocol.id || protocolIndex} className="grid gap-3 border-b pb-4 last:border-b-0 last:pb-0">
                        <div className="flex flex-col gap-3">
                          <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_32px_auto] xl:items-end">
                            <Field>
                              <FieldLabel>{locale === 'zh-CN' ? '协议' : 'Protocol'}</FieldLabel>
                              <NativeSelect className={selectClassName()} value={protocol.protocol} onChange={(event) => updateProtocol(protocolIndex, { protocol: event.target.value as ProtocolKind })}>
                                {protocolOptions.map((option) => {
                                  const takenByOtherRow = form.protocols.some((item, itemIndex) => itemIndex !== protocolIndex && item.protocol === option.value)
                                  return <NativeSelectOption key={option.value} value={option.value} disabled={takenByOtherRow}>{option.label}</NativeSelectOption>
                                })}
                              </NativeSelect>
                            </Field>
                            <Field>
                              <FieldLabel>{locale === 'zh-CN' ? '地址来源' : 'Base URL'}</FieldLabel>
                              <NativeSelect className={selectClassName()} value={protocol.base_url_id} onChange={(event) => updateProtocol(protocolIndex, { base_url_id: event.target.value })}>
                                <NativeSelectOption value="">{locale === 'zh-CN' ? '默认地址' : 'Default'}</NativeSelectOption>
                                {form.base_urls.map((item) => <NativeSelectOption key={item.id} value={item.id}>{item.name || item.url}</NativeSelectOption>)}
                              </NativeSelect>
                            </Field>
                            <Field>
                              <FieldLabel>{locale === 'zh-CN' ? '模型筛选密钥' : 'Model key'}</FieldLabel>
                              <NativeSelect className={selectClassName()} value={selectedCredentialId} onChange={(event) => updateProtocol(protocolIndex, { model_filter_credential_id: event.target.value || null })}>
                                {credentialOptions.length ? credentialOptions.map((item) => <NativeSelectOption key={item.id} value={item.id}>{item.display_name}</NativeSelectOption>) : <NativeSelectOption value="">{locale === 'zh-CN' ? '无可用密钥' : 'No key'}</NativeSelectOption>}
                              </NativeSelect>
                            </Field>
                            <div className="flex h-8 w-8 items-center justify-center xl:self-end">
                              <SwitchButton checked={protocol.enabled} onChange={(checked) => updateProtocol(protocolIndex, { enabled: checked })} />
                            </div>
                            <div className="flex flex-wrap items-center justify-end gap-2 xl:col-start-5 xl:row-start-1 xl:self-end">
                              <Button type="button" variant="outline" size="icon" className="text-muted-foreground" onClick={() => setAdvancedProtocolIndex(protocolIndex)}><Ellipsis size={16} /></Button>
                              <Button type="button" variant="outline" size="icon" className="text-destructive hover:text-destructive" onClick={() => setForm((current) => ({ ...current, protocols: current.protocols.length > 1 ? current.protocols.filter((_, currentIndex) => currentIndex !== protocolIndex) : current.protocols }))}><X size={16} /></Button>
                              <Button type="button" variant="ghost" size="default" className="text-muted-foreground hover:text-foreground" onClick={() => updateProtocol(protocolIndex, { expanded: !protocol.expanded })}>
                                <span>{locale === 'zh-CN' ? '模型列表' : 'Models'}</span>
                                <ChevronDown size={16} className={cn('transition-transform', protocol.expanded ? 'rotate-180' : '')} />
                              </Button>
                            </div>
                          </div>

                          {duplicatedProtocols.has(protocol.protocol) ? <div className="text-sm text-destructive">{locale === 'zh-CN' ? '协议类型重复' : 'Duplicate protocol'}</div> : null}

                          {protocol.expanded ? (
                            <div className="grid gap-3 pt-1">
                              <Separator />
                              <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto_auto] xl:items-end">
                                <Field>
                                  <FieldLabel>{locale === 'zh-CN' ? '模型名称' : 'Model name'}</FieldLabel>
                                  <Input
                                    className="min-w-[180px]"
                                    value={protocol.manual_model_name}
                                    onChange={(event) => updateProtocol(protocolIndex, { manual_model_name: event.target.value })}
                                    onKeyDown={(event) => {
                                      if (event.key !== 'Enter') return
                                      event.preventDefault()
                                      addManualProtocolModel(protocolIndex, selectedCredentialId)
                                    }}
                                    placeholder={locale === 'zh-CN' ? '模型名称' : 'Model name'}
                                  />
                                </Field>
                                <Field>
                                  <FieldLabel>{locale === 'zh-CN' ? '匹配规则' : 'Match regex'}</FieldLabel>
                                  <Input
                                    className="min-w-[180px]"
                                    value={protocol.match_regex}
                                    onChange={(event) => updateProtocol(protocolIndex, { match_regex: event.target.value })}
                                    placeholder={locale === 'zh-CN' ? '匹配规则' : 'Match regex'}
                                  />
                                </Field>
                                <Button type="button" variant="outline" onClick={() => addManualProtocolModel(protocolIndex, selectedCredentialId)} disabled={!selectedCredentialId || !protocol.manual_model_name.trim()}>
                                  {locale === 'zh-CN' ? '加入' : 'Add'}
                                </Button>
                                <Button type="button" variant="destructive" onClick={() => updateProtocol(protocolIndex, { models: [] })} disabled={!visibleModels.length}>{locale === 'zh-CN' ? '删除所有模型' : 'Remove all'}</Button>
                                <Button type="button" onClick={() => void fetchProtocolModels(protocolIndex)} disabled={fetchingProtocolIndex === protocolIndex || !form.base_urls.some((item) => item.enabled && item.url.trim()) || !activeCredentialIds.size}>
                                  <RefreshCcw size={14} className={fetchingProtocolIndex === protocolIndex ? 'animate-spin' : ''} />
                                  {locale === 'zh-CN' ? '刷新模型' : 'Refresh models'}
                                </Button>
                              </div>

                              <div className="flex flex-wrap items-center gap-2.5">
                                {visibleModels.length ? (
                                  <>
                                  {visibleModels.map(({ model, modelIndex }) => (
                                    <Button key={model.id || `${model.credential_id}-${model.model_name}-${modelIndex}`} type="button" variant="outline" size="sm" className={cn('rounded-full', modelBadgeClassName(model.enabled))} onClick={() => updateProtocol(protocolIndex, { models: protocol.models.filter((_, currentIndex) => currentIndex !== modelIndex) })}>
                                      <span>{model.model_name}</span>
                                      <X size={14} />
                                    </Button>
                                  ))}
                                  </>
                                ) : (
                                  <div className="text-sm text-muted-foreground">{locale === 'zh-CN' ? '当前没有模型' : 'No models selected'}</div>
                                )}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <div className="flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</Button>
              <Button type="submit">{editingSiteId ? (locale === 'zh-CN' ? '保存渠道' : 'Save channel') : (locale === 'zh-CN' ? '创建渠道' : 'Create channel')}</Button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog>

      <Dialog open={advancedProtocolIndex !== null} onOpenChange={(open) => { if (!open) setAdvancedProtocolIndex(null) }}>
        {advancedProtocolIndex !== null && form.protocols[advancedProtocolIndex] ? (
          <AppDialogContent className="max-w-3xl" title={locale === 'zh-CN' ? '更多设置' : 'More settings'}>
            <div className="grid gap-4">
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="protocol-proxy">{locale === 'zh-CN' ? '代理地址' : 'Proxy'}</FieldLabel>
                  <Input id="protocol-proxy" value={form.protocols[advancedProtocolIndex].channel_proxy} onChange={(event) => updateProtocol(advancedProtocolIndex, { channel_proxy: event.target.value })} placeholder="http://127.0.0.1:7890" />
                </Field>
              </FieldGroup>
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium text-foreground">{locale === 'zh-CN' ? '请求头' : 'Headers'}</div>
                  <Button type="button" variant="outline" size="sm" onClick={() => updateProtocol(advancedProtocolIndex, { headers: [...form.protocols[advancedProtocolIndex].headers, { key: '', value: '' }] })}>
                    <Plus data-icon="inline-start" />
                    {locale === 'zh-CN' ? '添加' : 'Add'}
                  </Button>
                </div>
                {form.protocols[advancedProtocolIndex].headers.map((header, headerIndex) => (
                  <div key={headerIndex} className="grid gap-3 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                    <Field>
                      <FieldLabel>{locale === 'zh-CN' ? '请求头名称' : 'Header key'}</FieldLabel>
                      <Input value={header.key} onChange={(event) => updateProtocolHeader(advancedProtocolIndex, headerIndex, { key: event.target.value })} placeholder={locale === 'zh-CN' ? '请求头名称' : 'Header-Key'} />
                    </Field>
                    <Field>
                      <FieldLabel>{locale === 'zh-CN' ? '请求头值' : 'Header value'}</FieldLabel>
                      <Input value={header.value} onChange={(event) => updateProtocolHeader(advancedProtocolIndex, headerIndex, { value: event.target.value })} placeholder={locale === 'zh-CN' ? '请求头值' : 'Header-Value'} />
                    </Field>
                    <Button type="button" variant="outline" size="icon" className="text-muted-foreground" onClick={() => updateProtocol(advancedProtocolIndex, { headers: form.protocols[advancedProtocolIndex].headers.length > 1 ? form.protocols[advancedProtocolIndex].headers.filter((_, currentIndex) => currentIndex !== headerIndex) : form.protocols[advancedProtocolIndex].headers })}><X size={16} /></Button>
                  </div>
                ))}
              </div>
              <Field>
                <FieldLabel htmlFor="protocol-param-override">{locale === 'zh-CN' ? '参数覆盖' : 'Param Override'}</FieldLabel>
                <Textarea id="protocol-param-override" className="min-h-24" value={form.protocols[advancedProtocolIndex].param_override} onChange={(event) => updateProtocol(advancedProtocolIndex, { param_override: event.target.value })} />
                <FieldDescription>{locale === 'zh-CN' ? '填写 JSON 片段用于覆盖请求参数。' : 'Use a JSON snippet to override request params.'}</FieldDescription>
              </Field>
            </div>
          </AppDialogContent>
        ) : null}
      </Dialog>

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除渠道' : 'Delete channel'} description={locale === 'zh-CN' ? '删除后该渠道下的协议、模型和模型组成员会一起移除。' : 'Protocol configs, models, and group members under this channel will be removed together.'}>
          <div className="grid gap-5">
            <div className="rounded-md border bg-muted/30 p-4">
              <strong className="text-foreground">{deleteTarget?.name}</strong>
              <p className="mt-2 text-xs text-muted-foreground">{deleteTarget ? siteSubtitle(deleteTarget) : ''}</p>
            </div>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</Button>
              <Button type="button" variant="destructive" onClick={() => deleteTarget && void removeSite(deleteTarget)} disabled={busyId === deleteTarget?.id}>{busyId === deleteTarget?.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '确认删除' : 'Delete')}</Button>
            </div>
          </div>
        </AppDialogContent>
      </Dialog>

      <Dialog open={modelPickerProtocolIndex !== null} onOpenChange={(open) => {
        if (!open) {
          closeModelPicker()
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
                      <Button key={key} type="button" variant="outline" size="sm" className={cn('max-w-full rounded-full', modelBadgeClassName(checked), checked ? 'border-primary text-primary' : '')} onClick={() => togglePickerModel(key)}>
                        <span className="max-w-[220px] truncate">{model.model_name}</span>
                        <span className="text-xs">{checked ? '✓' : '+'}</span>
                      </Button>
                    )
                  }) : <div className="px-3 py-6 text-sm text-muted-foreground">{locale === 'zh-CN' ? '未获取到可选模型' : 'No models fetched.'}</div>}
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => {
                  closeModelPicker()
                }}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</Button>
                <Button type="button" variant="outline" onClick={confirmAllModelSelection} disabled={!availableModels.length}>{locale === 'zh-CN' ? '加入全部模型' : 'Add all models'}</Button>
                <Button type="button" onClick={confirmModelSelection} disabled={!pickerSelectedModelKeys.length}>{locale === 'zh-CN' ? '加入模型' : 'Add models'}</Button>
              </div>
            </div>
          </AppDialogContent>
        ) : null}
      </Dialog>
    </section>
  )
}
