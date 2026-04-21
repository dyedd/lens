"use client"

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, AlertCircle, CheckCircle2, ChevronDown, Clock3, Ellipsis, Filter, Globe2, KeyRound, Plus, RefreshCcw, Server, Trash2, Waypoints, X } from 'lucide-react'
import { toast } from 'sonner'
import {
  ApiError,
  ProtocolKind,
  Site,
  SiteBaseUrlInput,
  SiteCredentialInput,
  SiteModelFetchItem,
  SiteModelFetchPayload,
  SitePayload,
  SiteProtocolCredentialBindingInput,
  SiteModelInput,
  SiteRuntimeSummary,
  apiRequest,
} from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet } from '@/components/ui/field'
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
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

type SiteRow = Site & {
  subtitle: string
  protocol_count: number
  credential_count: number
  model_count: number
  endpoint_summary: string
}

type ChannelStatusFilter = 'all' | 'enabled' | 'disabled'
type ChannelSort = 'requests-desc' | 'name-asc' | 'name-desc' | 'models-desc' | 'protocols-desc'
type SiteProtocolLike = Site['protocols'][number]

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

function siteEndpointSummary(site: Site, locale: string = 'zh-CN') {
  const enabled = site.base_urls.filter((item) => item.enabled)
  const firstUrl = enabled[0]?.url ?? site.base_urls[0]?.url ?? ''
  const extraCount = enabled.length > 1 ? enabled.length - 1 : (site.base_urls.length > 1 ? site.base_urls.length - 1 : 0)
  if (extraCount > 0) {
    const suffix = locale === 'zh-CN' ? ` + ${extraCount}个地址` : ` + ${extraCount} more`
    return firstUrl + suffix
  }
  return firstUrl
}

function siteModelCount(site: Site) {
  return site.protocols.reduce((total, protocol) => total + protocol.models.filter((item) => item.enabled).length, 0)
}

function isSiteEnabled(site: Site) {
  return site.protocols.some((item) => item.enabled)
}

function protocolBadgeClassName(protocol: ProtocolKind) {
  switch (protocol) {
    case 'openai_chat':
      return 'border-transparent bg-sky-500/10 text-sky-700'
    case 'openai_responses':
      return 'border-transparent bg-indigo-500/10 text-indigo-700'
    case 'anthropic':
      return 'border-transparent bg-amber-500/10 text-amber-700'
    case 'gemini':
      return 'border-transparent bg-emerald-500/10 text-emerald-700'
    default:
      return 'border-transparent bg-secondary text-secondary-foreground'
  }
}

function ChannelMetric({
  icon,
  label,
  value,
  tone = 'default',
}: {
  icon: React.ReactNode
  label: string
  value: string
  tone?: 'default' | 'accent'
}) {
  return (
    <div
      className={cn(
        'inline-flex min-h-8 items-center gap-2 rounded-full border px-3 text-xs',
        tone === 'accent'
          ? 'border-primary/20 bg-primary/[0.07] text-primary'
          : 'border-border/70 bg-muted/25 text-muted-foreground'
      )}
    >
      <span className="inline-flex size-4.5 items-center justify-center">{icon}</span>
      <span className="truncate font-medium">{label} {value}</span>
    </div>
  )
}

function getSiteFaviconCandidates(url: string) {
  try {
    const parsed = new URL(url)
    return [
      `${parsed.origin}/favicon.ico`,
      `https://www.google.com/s2/favicons?domain=${parsed.hostname}&sz=64`,
    ]
  } catch {
    return []
  }
}

function SiteFavicon({ url, name }: { url: string; name: string }) {
  const [candidateIndex, setCandidateIndex] = useState(0)
  const candidates = useMemo(() => getSiteFaviconCandidates(url), [url])
  const currentSrc = candidates[candidateIndex]

  return (
    <span className="flex size-11 items-center justify-center rounded-xl border bg-background/80">
      {currentSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={currentSrc}
          alt=""
          className="size-5 rounded-sm object-contain"
          loading="lazy"
          onError={() => {
            setCandidateIndex((current) => (current < candidates.length - 1 ? current + 1 : current))
          }}
        />
      ) : (
        <Globe2 aria-hidden="true" className="text-muted-foreground" />
      )}
      <span className="sr-only">{name}</span>
    </span>
  )
}

function formatRuntimeTimestamp(value: string, locale: 'zh-CN' | 'en-US') {
  return new Date(value).toLocaleString(locale === 'zh-CN' ? 'zh-CN' : 'en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function summarizeErrorMessage(value: string, maxLength = 120) {
  const singleLine = value.replace(/\s+/g, ' ').trim()
  if (singleLine.length <= maxLength) return singleLine
  return `${singleLine.slice(0, maxLength)}...`
}

function RecentRequestPreview({
  summary,
  locale,
}: {
  summary?: SiteRuntimeSummary
  locale: 'zh-CN' | 'en-US'
}) {
  if (!summary?.latest_request_at || summary.latest_success === null || summary.latest_success === undefined) {
    return (
      <div className="mt-3 text-xs text-muted-foreground">
        {locale === 'zh-CN' ? '最近暂无请求记录' : 'No recent requests'}
      </div>
    )
  }

  const isFailed = !summary.latest_success
  const errorMessage = summary.latest_error_message?.trim() || ''

  return (
    <div className="mt-3 grid gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant="outline"
          className={cn(
            'rounded-full border-0 px-2.5 py-0.5 text-xs font-medium',
            isFailed ? 'bg-destructive/12 text-destructive' : 'bg-primary/10 text-primary'
          )}
        >
          {isFailed
            ? (locale === 'zh-CN' ? '最近失败' : 'Latest failed')
            : (locale === 'zh-CN' ? '最近成功' : 'Latest success')}
        </Badge>
        {summary.latest_status_code !== null && summary.latest_status_code !== undefined ? (
          <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-medium">
            {summary.latest_status_code}
          </Badge>
        ) : null}
        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
          <Clock3 size={12} />
          {formatRuntimeTimestamp(summary.latest_request_at, locale)}
        </span>
      </div>

      {isFailed && errorMessage ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex max-w-full items-start gap-2 rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span className="truncate">{summarizeErrorMessage(errorMessage)}</span>
            </div>
          </TooltipTrigger>
          <TooltipContent className="max-w-sm whitespace-pre-wrap break-words" side="bottom" align="start">
            {errorMessage}
          </TooltipContent>
        </Tooltip>
      ) : (
        <div className="flex items-start gap-2 rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
          <CheckCircle2 size={14} className="mt-0.5 shrink-0" />
          <span>{locale === 'zh-CN' ? '最近一次请求正常' : 'The latest request completed normally'}</span>
        </div>
      )}
    </div>
  )
}

function protocolFilterStorageKey(siteId: string, protocolId: string) {
  return `lens:channel-model-filter:${siteId}:${protocolId}`
}

function readStoredProtocolFilter(siteId: string, protocolId: string) {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(protocolFilterStorageKey(siteId, protocolId))
}

function writeStoredProtocolFilter(siteId: string, protocolId: string, credentialId: string | null) {
  if (typeof window === 'undefined') return
  const key = protocolFilterStorageKey(siteId, protocolId)
  if (!credentialId) {
    window.localStorage.removeItem(key)
    return
  }
  window.localStorage.setItem(key, credentialId)
}

function inferProtocolFilterCredential(siteId: string, protocol: SiteProtocolLike) {
  const availableCredentialIds = new Set(protocol.bindings.filter((binding) => binding.enabled).map((binding) => binding.credential_id))
  const stored = readStoredProtocolFilter(siteId, protocol.id)
  if (stored && availableCredentialIds.has(stored)) {
    return stored
  }

  const modelCredentialId = protocol.models.find((model) => model.enabled && availableCredentialIds.has(model.credential_id))?.credential_id
    ?? protocol.models.find((model) => availableCredentialIds.has(model.credential_id))?.credential_id
  if (modelCredentialId) {
    return modelCredentialId
  }

  const firstEnabledBinding = protocol.bindings.find((binding) => binding.enabled)?.credential_id
  return firstEnabledBinding ?? null
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
      model_filter_credential_id: inferProtocolFilterCredential(site.id, item),
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
  const [statusFilter, setStatusFilter] = useState<ChannelStatusFilter>('all')
  const [protocolFilter, setProtocolFilter] = useState<'all' | ProtocolKind>('all')
  const [sortBy, setSortBy] = useState<ChannelSort>('requests-desc')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Site | null>(null)
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [fetchingProtocolIndex, setFetchingProtocolIndex] = useState<number | null>(null)
  const [advancedProtocolIndex, setAdvancedProtocolIndex] = useState<number | null>(null)
  const [modelPickerProtocolIndex, setModelPickerProtocolIndex] = useState<number | null>(null)
  const [availableModels, setAvailableModels] = useState<PickerModelItem[]>([])
  const [pickerSelectedModelKeys, setPickerSelectedModelKeys] = useState<string[]>([])
  const [formSnapshot, setFormSnapshot] = useState('')

  const { data: sites, isLoading } = useQuery({
    queryKey: ['sites'],
    queryFn: () => apiRequest<Site[]>('/admin/sites'),
    staleTime: 2 * 60_000,
  })
  const { data: siteRuntimeSummaries } = useQuery({
    queryKey: ['site-runtime-summaries'],
    queryFn: () => apiRequest<SiteRuntimeSummary[]>('/admin/sites/runtime'),
    staleTime: 5_000,
    refetchInterval: 5000,
  })

  const siteRuntimeById = useMemo(
    () => new Map((siteRuntimeSummaries ?? []).map((item) => [item.site_id, item] as const)),
    [siteRuntimeSummaries]
  )
  const siteRows = useMemo<SiteRow[]>(() => (
    (sites ?? []).map((site) => ({
      ...site,
      subtitle: siteSubtitle(site),
      protocol_count: site.protocols.filter((p) => p.enabled).length,
      credential_count: site.credentials.length,
      model_count: siteModelCount(site),
      endpoint_summary: siteEndpointSummary(site, locale),
    }))
  ), [sites, locale])
  const visibleSites = useMemo<SiteRow[]>(() => {
    const keyword = search.trim().toLowerCase()
    const filtered = siteRows.filter((site) => {
      if (statusFilter === 'enabled' && !isSiteEnabled(site)) return false
      if (statusFilter === 'disabled' && isSiteEnabled(site)) return false
      if (protocolFilter !== 'all' && !site.protocols.some((item) => item.protocol === protocolFilter)) return false
      if (!keyword) return true
      const stack = [site.name, site.subtitle, site.endpoint_summary, ...site.protocols.flatMap((item) => item.models.map((model) => model.model_name))].join(' ').toLowerCase()
      return stack.includes(keyword)
    })

      return [...filtered].sort((left, right) => {
        const leftRequestCount = siteRuntimeById.get(left.id)?.recent_request_count ?? 0
        const rightRequestCount = siteRuntimeById.get(right.id)?.recent_request_count ?? 0
        if (sortBy === 'name-asc') return left.name.localeCompare(right.name, locale)
        if (sortBy === 'name-desc') return right.name.localeCompare(left.name, locale)
        if (sortBy === 'models-desc') return right.model_count - left.model_count || left.name.localeCompare(right.name, locale)
        if (sortBy === 'protocols-desc') return right.protocol_count - left.protocol_count || left.name.localeCompare(right.name, locale)
        return rightRequestCount - leftRequestCount || left.name.localeCompare(right.name, locale)
      })
  }, [locale, protocolFilter, search, siteRows, siteRuntimeById, sortBy, statusFilter])
  const activeFilterCount = [
    Boolean(search.trim()),
    statusFilter !== 'all',
    protocolFilter !== 'all',
  ].filter(Boolean).length
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
      queryClient.invalidateQueries({ queryKey: ['site-runtime-summaries'] }),
      queryClient.invalidateQueries({ queryKey: ['group-candidates'] }),
    ])
  }

  function applyPreparedForm(nextForm: FormState) {
    setForm(nextForm)
    setFormSnapshot(JSON.stringify(toPayload(nextForm)))
  }

  function confirmDiscardChanges() {
    if (!hasUnsavedChanges) return true
    return window.confirm(locale === 'zh-CN' ? '当前有未保存修改，确定离开吗？' : 'You have unsaved changes. Leave anyway?')
  }

  function openCreate() {
    if (!confirmDiscardChanges()) return
    setEditingSiteId(null)
    applyPreparedForm(emptyForm())
    setDialogOpen(true)
  }

  function openEdit(site: Site) {
    if (!confirmDiscardChanges()) return
    setEditingSiteId(site.id)
    applyPreparedForm(toForm(site))
    setDialogOpen(true)
  }

  function closeEditor() {
    if (!confirmDiscardChanges()) return
    setDialogOpen(false)
    setEditingSiteId(null)
  }

  function updateProtocolFilter(protocolIndex: number, credentialId: string | null) {
    const protocol = form.protocols[protocolIndex]
    if (editingSiteId && protocol?.id) {
      writeStoredProtocolFilter(editingSiteId, protocol.id, credentialId)
    }
    updateProtocol(protocolIndex, { model_filter_credential_id: credentialId })
  }

  function resetFilters() {
    setSearch('')
    setStatusFilter('all')
    setProtocolFilter('all')
    setSortBy('requests-desc')
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const duplicatedProtocols = duplicateProtocolKinds(form.protocols)
    if (duplicatedProtocols.size) {
      const message = locale === 'zh-CN' ? '同一个渠道内不允许重复协议' : 'Duplicate protocols are not allowed in one channel'
      toast.error(message)
      return
    }
    try {
      const savedSite = await apiRequest<Site>(editingSiteId ? `/admin/sites/${editingSiteId}` : '/admin/sites', {
        method: editingSiteId ? 'PUT' : 'POST',
        body: JSON.stringify(toPayload(form)),
      })
      queryClient.setQueryData<Site[]>(['sites'], (current) => {
        const rows = current ?? []
        const exists = rows.some((site) => site.id === savedSite.id)
        return exists ? rows.map((site) => site.id === savedSite.id ? savedSite : site) : [savedSite, ...rows]
      })
      applyPreparedForm(toForm(savedSite))
      setDialogOpen(false)
      setEditingSiteId(null)
      toast.success(editingSiteId
        ? (locale === 'zh-CN' ? '渠道已更新' : 'Channel updated')
        : (locale === 'zh-CN' ? '渠道已创建' : 'Channel created'))
      await invalidateChannelData()
    } catch (e) {
      const message = e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存渠道失败' : 'Failed to save channel')
      toast.error(message)
    }
  }

  async function removeSite(site: Site) {
    setBusyId(site.id)
    try {
      await apiRequest<void>(`/admin/sites/${site.id}`, { method: 'DELETE' })
      queryClient.setQueryData<Site[]>(['sites'], (current) => (current ?? []).filter((item) => item.id !== site.id))
      setDeleteTarget(null)
      if (editingSiteId === site.id) {
        setDialogOpen(false)
        setEditingSiteId(null)
      }
      toast.success(locale === 'zh-CN' ? '渠道已删除' : 'Channel deleted')
      await invalidateChannelData()
    } catch (e) {
      const message = e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除渠道失败' : 'Failed to delete channel')
      toast.error(message)
    } finally {
      setBusyId(null)
    }
  }

  async function toggleSiteEnabled(site: Site, enabled: boolean) {
    setBusyId(site.id)
    try {
      const updatedSite = await apiRequest<Site>(`/admin/sites/${site.id}`, {
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
      queryClient.setQueryData<Site[]>(['sites'], (current) => (current ?? []).map((item) => item.id === updatedSite.id ? updatedSite : item))
      toast.success(enabled
        ? (locale === 'zh-CN' ? '渠道已启用' : 'Channel enabled')
        : (locale === 'zh-CN' ? '渠道已停用' : 'Channel disabled'))
      await invalidateChannelData()
    } catch (e) {
      const message = e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '更新渠道状态失败' : 'Failed to update channel status')
      toast.error(message)
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
    if (selectedModels.length) {
      toast.success(locale === 'zh-CN' ? `已加入 ${selectedModels.length} 个模型` : `Added ${selectedModels.length} models`)
    }
  }

  async function fetchProtocolModels(protocolIndex: number) {
    const protocol = form.protocols[protocolIndex]
    if (!protocol) return
    const activeCredentials = form.credentials.filter((item) => item.enabled && item.api_key.trim()).map((item, index) => ({ ...item, display_name: credentialLabel(item, index, locale) }))
    const selectedCredentialId = activeCredentials.some((item) => item.id === protocol.model_filter_credential_id)
      ? protocol.model_filter_credential_id || ''
      : activeCredentials[0]?.id || ''
    setFetchingProtocolIndex(protocolIndex)
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
      toast.success(locale === 'zh-CN' ? `已获取 ${models.length} 个模型` : `Fetched ${models.length} models`)
    } catch (e) {
      const message = e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '刷新模型失败' : 'Failed to refresh models')
      toast.error(message)
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

  return (
    <TooltipProvider>
      <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">{locale === 'zh-CN' ? '渠道' : 'Channels'}</h1>
        <Button type="button" onClick={openCreate} className="rounded-full" size="icon-sm" title={locale === 'zh-CN' ? '新建渠道' : 'New channel'}>
          <Plus size={18} />
        </Button>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_320px]">
        <Card className="min-h-[calc(100dvh-12rem)] overflow-hidden py-0">
          <CardContent className="max-h-[calc(100dvh-12rem)] overflow-y-auto px-3 py-3">
            {isLoading ? (
              <div className="px-2 py-6 text-sm text-muted-foreground">{locale === 'zh-CN' ? '正在加载渠道...' : 'Loading channels...'}</div>
            ) : visibleSites.length ? (
              <ItemGroup className="gap-3">
                {visibleSites.map((site) => {
                  const runtimeSummary = siteRuntimeById.get(site.id)
                  return (
                    <Item
                      key={site.id}
                      variant="outline"
                      role="button"
                      tabIndex={0}
                      className="items-start gap-4 rounded-2xl border-border/80 bg-gradient-to-r from-background to-muted/[0.18] px-5 py-5 shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer"
                      onClick={() => openEdit(site)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          openEdit(site)
                        }
                      }}
                    >
                      <ItemMedia variant="icon" className="mt-0.5 self-start">
                        <SiteFavicon key={site.endpoint_summary} url={site.endpoint_summary} name={site.name} />
                      </ItemMedia>
                      <ItemContent className="min-w-0">
                        <div className="flex flex-col gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <ItemTitle className="truncate text-base">{site.name}</ItemTitle>
                            {site.protocols.map((protocol) => (
                              <Badge
                                key={protocol.id}
                                variant="outline"
                                className={cn('px-2.5 py-0.5', protocolBadgeClassName(protocol.protocol))}
                              >
                                {protocolLabel(protocol.protocol)}
                              </Badge>
                            ))}
                          </div>
                          <ItemDescription className="truncate text-sm">
                            {site.endpoint_summary || (locale === 'zh-CN' ? '未配置请求地址' : 'No endpoint configured')}
                          </ItemDescription>
                          <RecentRequestPreview summary={runtimeSummary} locale={locale} />
                        </div>
                        <ItemFooter className="mt-4 flex flex-wrap items-center gap-2.5">
                          <ChannelMetric icon={<Activity size={14} />} label={locale === 'zh-CN' ? '请求数' : 'Requests'} value={String(runtimeSummary?.recent_request_count ?? 0)} />
                          <ChannelMetric icon={<Waypoints size={14} />} label={locale === 'zh-CN' ? '协议' : 'Protocols'} value={String(site.protocol_count)} />
                          <ChannelMetric icon={<Server size={14} />} label={locale === 'zh-CN' ? '模型' : 'Models'} value={String(site.model_count)} />
                          <ChannelMetric icon={<KeyRound size={14} />} label={locale === 'zh-CN' ? '密钥' : 'Keys'} value={String(site.credential_count)} />
                        </ItemFooter>
                      </ItemContent>
                      <ItemActions
                        className="ml-auto self-start"
                        onClick={(event) => event.stopPropagation()}
                        onKeyDown={(event) => event.stopPropagation()}
                      >
                        <SwitchButton checked={isSiteEnabled(site)} disabled={busyId === site.id} onChange={(checked) => void toggleSiteEnabled(site, checked)} />
                        <Button type="button" variant="ghost" size="sm" className="rounded-full text-destructive hover:text-destructive" onClick={() => setDeleteTarget(site)}>
                          <Trash2 data-icon="inline-start" />
                          {locale === 'zh-CN' ? '删除' : 'Delete'}
                        </Button>
                      </ItemActions>
                    </Item>
                  )
                })}
              </ItemGroup>
            ) : (
              <div className="rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">
                {search.trim()
                  ? (locale === 'zh-CN' ? '没有匹配的渠道。' : 'No matching channels.')
                  : (locale === 'zh-CN' ? '当前还没有渠道。' : 'No channels yet.')}
              </div>
            )}
          </CardContent>
        </Card>

        <aside className="order-1 xl:order-2">
          <div className="rounded-2xl border bg-card p-4 xl:sticky xl:top-4">
            <div className="mb-4 flex items-center justify-between gap-3">
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
              <Button type="button" variant="ghost" size="sm" onClick={resetFilters} disabled={!activeFilterCount && sortBy === 'requests-desc'}>
                {locale === 'zh-CN' ? '清空' : 'Clear'}
              </Button>
            </div>

            <FieldSet className="gap-4">
              <FieldLegend>{locale === 'zh-CN' ? '筛选条件' : 'Refine results'}</FieldLegend>
              <FieldGroup className="gap-4">
                <Field>
                  <FieldLabel>{locale === 'zh-CN' ? '关键词' : 'Keyword'}</FieldLabel>
                  <ToolbarSearchInput
                    value={search}
                    onChange={setSearch}
                    onClear={() => setSearch('')}
                    placeholder={locale === 'zh-CN' ? '渠道 / 协议 / 模型' : 'Channel / protocol / model'}
                    className="max-w-none"
                  />
                </Field>

                <Field>
                  <FieldLabel>{locale === 'zh-CN' ? '状态' : 'Status'}</FieldLabel>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { key: 'all' as const, label: locale === 'zh-CN' ? '全部' : 'All' },
                      { key: 'enabled' as const, label: locale === 'zh-CN' ? '启用' : 'Enabled' },
                      { key: 'disabled' as const, label: locale === 'zh-CN' ? '停用' : 'Disabled' },
                    ].map((option) => (
                      <Button
                        key={option.key}
                        type="button"
                        variant={statusFilter === option.key ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setStatusFilter(option.key)}
                      >
                        {option.label}
                      </Button>
                    ))}
                  </div>
                </Field>

                <Field>
                  <FieldLabel htmlFor="channels-protocol-filter">{locale === 'zh-CN' ? '协议' : 'Protocol'}</FieldLabel>
                  <NativeSelect
                    id="channels-protocol-filter"
                    className="w-full"
                    value={protocolFilter}
                    onChange={(event) => setProtocolFilter(event.target.value as 'all' | ProtocolKind)}
                  >
                    <NativeSelectOption value="all">{locale === 'zh-CN' ? '全部协议' : 'All protocols'}</NativeSelectOption>
                    {protocolOptions.map((option) => (
                      <NativeSelectOption key={option.value} value={option.value}>{option.label}</NativeSelectOption>
                    ))}
                  </NativeSelect>
                </Field>

                <Field>
                  <FieldLabel htmlFor="channels-sort">{locale === 'zh-CN' ? '排序' : 'Sort by'}</FieldLabel>
                  <NativeSelect
                    id="channels-sort"
                    className="w-full"
                    value={sortBy}
                    onChange={(event) => setSortBy(event.target.value as ChannelSort)}
                  >
                    <NativeSelectOption value="requests-desc">{locale === 'zh-CN' ? '请求优先' : 'Requests first'}</NativeSelectOption>
                    <NativeSelectOption value="models-desc">{locale === 'zh-CN' ? '模型优先' : 'Models first'}</NativeSelectOption>
                    <NativeSelectOption value="protocols-desc">{locale === 'zh-CN' ? '协议优先' : 'Protocols first'}</NativeSelectOption>
                    <NativeSelectOption value="name-asc">{locale === 'zh-CN' ? '名称升序' : 'Name asc'}</NativeSelectOption>
                    <NativeSelectOption value="name-desc">{locale === 'zh-CN' ? '名称降序' : 'Name desc'}</NativeSelectOption>
                  </NativeSelect>
                </Field>
              </FieldGroup>
            </FieldSet>
          </div>
        </aside>
      </div>

      <Dialog open={dialogOpen} onOpenChange={(open) => {
        if (!open && hasUnsavedChanges) {
          const confirmed = window.confirm(locale === 'zh-CN' ? '当前有未保存修改，确定关闭吗？' : 'You have unsaved changes. Close anyway?')
          if (!confirmed) return
        }
        setDialogOpen(open)
        if (!open) {
          setEditingSiteId(null)
        }
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
                              <NativeSelect className={selectClassName()} value={selectedCredentialId} onChange={(event) => updateProtocolFilter(protocolIndex, event.target.value || null)}>
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
            <div className="flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={closeEditor}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</Button>
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
    </TooltipProvider>
  )
}
