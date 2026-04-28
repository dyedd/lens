"use client"

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, Filter, GripVertical, LayoutGrid, Plus, RefreshCcw, Search, Sparkles, Trash2, X } from 'lucide-react'
import { toast } from 'sonner'
import {
  ApiError,
  ModelGroup,
  ModelGroupCandidateItem,
  ModelGroupCandidatesPayload,
  ModelGroupCandidatesResponse,
  ModelGroupPayload,
  ProtocolKind,
  RoutingStrategy,
  Site,
  apiRequest,
} from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { getModelGroupAvatar, ModelAvatar } from '@/lib/model-icons'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Field, FieldGroup, FieldLabel, FieldLegend, FieldSet } from '@/components/ui/field'
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
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ToolbarSearchInput } from '@/components/ui/toolbar-search-input'

type FormItem = {
  channel_id: string
  channel_name: string
  credential_id: string
  credential_name: string
  model_name: string
  enabled: boolean
}

type FormState = {
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  route_group_id: string
  input_price_per_million: string
  output_price_per_million: string
  cache_read_price_per_million: string
  cache_write_price_per_million: string
  items: FormItem[]
}

type CandidateChannel = {
  channel_id: string
  channel_name: string
  credentials: Array<{
    credential_id: string
    credential_name: string
    items: ModelGroupCandidateItem[]
  }>
}

type GroupSort = 'members-desc' | 'enabled-desc' | 'name-asc' | 'name-desc'

type GroupRow = ModelGroup & {
  member_count: number
  enabled_member_count: number
  channel_summary: string
  channel_names: string[]
  is_route_group: boolean
}

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

const emptyForm: FormState = {
  name: '',
  protocol: 'openai_chat',
  strategy: 'round_robin',
  route_group_id: '',
  input_price_per_million: '0',
  output_price_per_million: '0',
  cache_read_price_per_million: '0',
  cache_write_price_per_million: '0',
  items: [],
}

function compileCandidateSearchRegex(value: string) {
  const normalized = value.trim()
  if (!normalized) {
    return null
  }
  if (normalized.startsWith('re:')) {
    try {
      return new RegExp(normalized.slice(3).trim(), 'i')
    } catch {
      return null
    }
  }
  if (!normalized.startsWith('/')) {
    return null
  }
  const lastSlashIndex = normalized.lastIndexOf('/')
  if (lastSlashIndex <= 0) {
    return null
  }
  const pattern = normalized.slice(1, lastSlashIndex)
  const flags = normalized.slice(lastSlashIndex + 1) || 'i'
  try {
    return new RegExp(pattern, flags)
  } catch {
    return null
  }
}

function matchesCandidateSearch(haystack: string, keyword: string) {
  const normalizedKeyword = keyword.trim()
  if (!normalizedKeyword) {
    return true
  }
  const regex = compileCandidateSearchRegex(normalizedKeyword)
  if (regex) {
    return regex.test(haystack)
  }
  return haystack.toLowerCase().includes(normalizedKeyword.toLowerCase())
}

function normalizeModelName(value: string | null | undefined) {
  return (value || '').trim().toLowerCase()
}

function getSeriesPreset(name: string) {
  const normalized = normalizeModelName(name)
  return MODEL_SERIES_PRESETS.find((item) => item.key !== 'other' && item.prefixes.some((prefix) => normalized.startsWith(prefix))) ?? MODEL_SERIES_PRESETS.find((item) => item.key === 'other')!
}

function getSeriesKey(group: Pick<ModelGroup, 'name'>): ModelSeriesKey {
  return getSeriesPreset(group.name).key
}

const strategyOptions: Array<{ value: RoutingStrategy; zh: string; en: string }> = [
  { value: 'round_robin', zh: '轮询', en: 'Round Robin' },
  { value: 'failover', zh: '故障转移', en: 'Failover' },
]

const protocolLabels: Record<ProtocolKind, { zh: string; en: string }> = {
  openai_chat: { zh: 'OpenAI Chat', en: 'OpenAI Chat' },
  openai_responses: { zh: 'OpenAI Responses', en: 'OpenAI Responses' },
  anthropic: { zh: 'Anthropic', en: 'Anthropic' },
  gemini: { zh: 'Gemini', en: 'Gemini' },
}

function protocolLabel(protocol: ProtocolKind, locale: 'zh-CN' | 'en-US') {
  return protocolLabels[protocol][locale === 'zh-CN' ? 'zh' : 'en']
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

function protocolOptions(locale: 'zh-CN' | 'en-US') {
  return (Object.keys(protocolLabels) as ProtocolKind[]).map((value) => ({
    value,
    label: protocolLabel(value, locale),
  }))
}

function panelClassName(extra = '') {
  return cn('rounded-lg bg-muted/10', extra)
}

function formatMoney(value: number) {
  if (value === 0) return '0'
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: value >= 1 ? 2 : 0,
    maximumFractionDigits: 4,
  }).format(value)
}

function metricLabel(
  key: 'input' | 'output' | 'cache_read' | 'cache_write',
  locale: 'zh-CN' | 'en-US'
) {
  const labels: Record<'input' | 'output' | 'cache_read' | 'cache_write', { zh: string; en: string }> = {
    input: { zh: '输入', en: 'Input' },
    output: { zh: '输出', en: 'Output' },
    cache_read: { zh: '缓存读取', en: 'Cache Read' },
    cache_write: { zh: '缓存写入', en: 'Cache Write' },
  }

  return labels[key][locale === 'zh-CN' ? 'zh' : 'en']
}

function compactMetricLabel(
  key: 'input' | 'output' | 'cache_read' | 'cache_write',
  locale: 'zh-CN' | 'en-US'
) {
  const labels: Record<'input' | 'output' | 'cache_read' | 'cache_write', { zh: string; en: string }> = {
    input: { zh: '输入', en: 'IN' },
    output: { zh: '输出', en: 'OUT' },
    cache_read: { zh: '读', en: 'CR' },
    cache_write: { zh: '写', en: 'CW' },
  }

  return labels[key][locale === 'zh-CN' ? 'zh' : 'en']
}

function selectClassName() {
  return 'w-full [&_select]:border-border [&_select]:bg-background [&_select]:text-sm [&_select]:text-foreground'
}

function itemKey(item: Pick<FormItem, 'channel_id' | 'credential_id' | 'model_name'>) {
  return `${item.channel_id}::${item.credential_id}::${item.model_name}`
}

function isGroupEnabled(group: Pick<GroupRow, 'enabled_member_count' | 'is_route_group'>) {
  return group.is_route_group || group.enabled_member_count > 0
}

function moveItems<T>(items: T[], fromIndex: number, toIndex: number) {
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0 || fromIndex >= items.length || toIndex >= items.length) {
    return items
  }
  const nextItems = items.slice()
  const [target] = nextItems.splice(fromIndex, 1)
  nextItems.splice(toIndex, 0, target)
  return nextItems
}

type ProtocolMeta = {
  id: string
  name: string
  base_url: string
  protocol: ProtocolKind
}

function channelEndpoint(channel?: ProtocolMeta) {
  if (!channel) return ''
  return channel.base_url || ''
}

function toForm(group: ModelGroup): FormState {
  return {
    name: group.name,
    protocol: group.protocol,
    strategy: group.strategy,
    route_group_id: group.route_group_id ?? '',
    input_price_per_million: String(group.input_price_per_million),
    output_price_per_million: String(group.output_price_per_million),
    cache_read_price_per_million: String(group.cache_read_price_per_million),
    cache_write_price_per_million: String(group.cache_write_price_per_million),
    items: group.items
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((item) => ({
        channel_id: item.channel_id,
        channel_name: item.channel_name,
        credential_id: item.credential_id,
        credential_name: item.credential_name,
        model_name: item.model_name,
        enabled: item.enabled,
      })),
  }
}

function toPayload(form: FormState): ModelGroupPayload {
  return {
    name: form.name.trim(),
    protocol: form.protocol,
    strategy: form.strategy,
    route_group_id: form.route_group_id.trim(),
    items: form.items.map((item) => ({ channel_id: item.channel_id, credential_id: item.credential_id, model_name: item.model_name, enabled: item.enabled })),
  }
}

function SwitchButton({ checked, disabled, onChange }: { checked: boolean; disabled?: boolean; onChange: (checked: boolean) => void }) {
  return <Switch checked={checked} disabled={disabled} onCheckedChange={onChange} />
}

function CompactPriceSummary({
  locale,
  inputPrice,
  outputPrice,
  cacheReadPrice,
  cacheWritePrice,
}: {
  locale: 'zh-CN' | 'en-US'
  inputPrice: number
  outputPrice: number
  cacheReadPrice: number
  cacheWritePrice: number
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="mt-2 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <span>{compactMetricLabel('input', locale)} ${formatMoney(inputPrice)}</span>
          <span>{compactMetricLabel('output', locale)} ${formatMoney(outputPrice)}</span>
          <span>{compactMetricLabel('cache_read', locale)} ${formatMoney(cacheReadPrice)}</span>
          <span>{compactMetricLabel('cache_write', locale)} ${formatMoney(cacheWritePrice)}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" align="start">
        <div className="grid gap-1">
          <div>{metricLabel('input', locale)}: ${formatMoney(inputPrice)} / 1M tokens</div>
          <div>{metricLabel('output', locale)}: ${formatMoney(outputPrice)} / 1M tokens</div>
          <div>{metricLabel('cache_read', locale)}: ${formatMoney(cacheReadPrice)} / 1M tokens</div>
          <div>{metricLabel('cache_write', locale)}: ${formatMoney(cacheWritePrice)} / 1M tokens</div>
        </div>
      </TooltipContent>
    </Tooltip>
  )
}

function EditablePriceRow({
  locale,
  primaryLabel,
  primaryValue,
  secondaryLabel,
  secondaryValue,
  onPrimaryChange,
  onSecondaryChange,
}: {
  locale: 'zh-CN' | 'en-US'
  primaryLabel: 'input' | 'output'
  primaryValue: string
  secondaryLabel: 'cache_read' | 'cache_write'
  secondaryValue: string
  onPrimaryChange: (value: string) => void
  onSecondaryChange: (value: string) => void
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field className="min-w-0">
        <FieldLabel>${metricLabel(primaryLabel, locale)}</FieldLabel>
        <Input className="mt-2" value={primaryValue} onChange={(event) => onPrimaryChange(event.target.value)} />
      </Field>

      <Field className="min-w-0">
        <FieldLabel>${metricLabel(secondaryLabel, locale)}</FieldLabel>
        <Input className="mt-2" value={secondaryValue} onChange={(event) => onSecondaryChange(event.target.value)} />
      </Field>
    </div>
  )
}

function StrategyToggle({
  value,
  locale,
  disabled = false,
  size = 'default',
  className,
  onChange,
}: {
  value: RoutingStrategy
  locale: 'zh-CN' | 'en-US'
  disabled?: boolean
  size?: 'default' | 'sm'
  className?: string
  onChange: (value: RoutingStrategy) => void
}) {
  return (
    <ToggleGroup
      type="single"
      value={value}
      onValueChange={(nextValue) => {
        if (nextValue) {
          onChange(nextValue as RoutingStrategy)
        }
      }}
      variant="outline"
      size={size}
      spacing={1}
      className={cn('max-w-full flex-wrap', className)}
    >
      {strategyOptions.map((option) => (
        <ToggleGroupItem key={option.value} value={option.value} disabled={disabled} className="max-w-full">
          {locale === 'zh-CN' ? option.zh : option.en}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}

function CandidateRow({
  item,
  active,
  onClick,
}: {
  item: ModelGroupCandidateItem
  active: boolean
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      className={cn(
        'h-8 w-full justify-between rounded-md px-3 text-left',
        active ? 'cursor-not-allowed opacity-60' : 'hover:bg-muted'
      )}
      onClick={onClick}
      disabled={active}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">{item.model_name}</div>
      </div>
      <span className="shrink-0 text-muted-foreground">{active ? <Check size={15} className="text-primary" /> : <Plus size={15} />}</span>
    </Button>
  )
}

function SelectedMemberRow({
  item,
  index,
  dragging,
  busy,
  onToggle,
  onRemove,
  onDragStart,
  onDragEnter,
  onDragEnd,
}: {
  item: FormItem
  index: number
  dragging: boolean
  busy: boolean
  onToggle: () => void
  onRemove: () => void
  onDragStart: () => void
  onDragEnter: () => void
  onDragEnd: () => void
}) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnter={onDragEnter}
      onDragOver={(event) => event.preventDefault()}
      onDragEnd={onDragEnd}
      className={cn(
        'flex min-w-0 items-center gap-2 border-b px-2.5 py-2 transition last:border-b-0',
        dragging && 'opacity-60 shadow-sm',
        !item.enabled && 'opacity-55'
      )}
    >
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-primary/10 text-xs font-semibold text-primary">{index + 1}</span>
      <span className="cursor-grab text-muted-foreground active:cursor-grabbing">
        <GripVertical size={14} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">{item.model_name}</div>
        <div className="truncate text-xs text-muted-foreground">{item.channel_name}{!item.enabled ? ' · 已关闭' : ''}</div>
      </div>
      <div className="flex h-8 w-8 items-center justify-center">
        <SwitchButton checked={item.enabled} disabled={busy} onChange={onToggle} />
      </div>
      <Button type="button" variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive" onClick={onRemove}>
        <X size={13} />
      </Button>
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

export function GroupsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const [selectedSeries, setSelectedSeries] = useState<SelectedSeries>('all')
  const [search, setSearch] = useState('')
  const [protocolFilter, setProtocolFilter] = useState<'all' | ProtocolKind>('all')
  const [strategyFilter, setStrategyFilter] = useState<'all' | RoutingStrategy>('all')
  const [sortBy, setSortBy] = useState<GroupSort>('members-desc')
  const [candidateSearch, setCandidateSearch] = useState('')
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null)
  const [expandedChannels, setExpandedChannels] = useState<string[]>([])
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null)
  const [cardDragging, setCardDragging] = useState<{ groupId: string; index: number } | null>(null)
  const [showEnabledOnly, setShowEnabledOnly] = useState(false)
  const [syncingPrices, setSyncingPrices] = useState(false)
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)

  const { data: groups, isLoading } = useQuery({
    queryKey: ['groups'],
    queryFn: () => apiRequest<ModelGroup[]>('/admin/model-groups'),
    staleTime: 2 * 60_000,
  })
  const { data: sites } = useQuery({
    queryKey: ['sites'],
    queryFn: () => apiRequest<Site[]>('/admin/sites'),
    staleTime: 2 * 60_000,
  })
  const candidatePayload: ModelGroupCandidatesPayload = useMemo(() => ({
    protocol: form.protocol,
    exclude_items: form.items.map((item) => ({ channel_id: item.channel_id, credential_id: item.credential_id, model_name: item.model_name, enabled: item.enabled })),
  }), [form.items, form.protocol])
  const { data: candidateResponse, refetch: refetchCandidates, isFetching: isFetchingCandidates } = useQuery({
    queryKey: ['group-candidates', candidatePayload],
    queryFn: () => apiRequest<ModelGroupCandidatesResponse>('/admin/model-group-candidates', {
      method: 'POST',
      body: JSON.stringify(candidatePayload),
    }),
    enabled: dialogOpen && !form.route_group_id,
  })

  const channelMap = useMemo(() => {
    const map = new Map<string, ProtocolMeta>()
    for (const site of sites ?? []) {
      const activeBaseUrl = site.base_urls.find((item) => item.enabled)?.url || site.base_urls[0]?.url || ''
      for (const protocol of site.protocols) {
        map.set(protocol.id, {
          id: protocol.id,
          name: site.name,
          base_url: activeBaseUrl,
          protocol: protocol.protocol,
        })
      }
    }
    return map
  }, [sites])

  const groupRows = useMemo<GroupRow[]>(() => (
    (groups ?? []).map((group) => {
      const isRouteGroup = Boolean(group.route_group_id)
      const items = group.items.slice().sort((a, b) => a.sort_order - b.sort_order)
      const channelNames = isRouteGroup
        ? [group.route_group_name || group.route_group_id || '']
        : [...new Set(items.map((item) => item.channel_name || channelMap.get(item.channel_id)?.name || item.channel_id).filter(Boolean))]
      return {
        ...group,
        items,
        member_count: isRouteGroup ? 1 : items.length,
        enabled_member_count: isRouteGroup ? 1 : items.filter((item) => item.enabled).length,
        channel_summary: channelNames.slice(0, 2).join(' · '),
        channel_names: channelNames,
        is_route_group: isRouteGroup,
      }
    })
  ), [channelMap, groups])

  const routeTargetOptions = useMemo(() => (
    (groups ?? [])
      .filter((group) => group.protocol === form.protocol && !group.route_group_id && group.id !== editingId)
      .sort((left, right) => left.name.localeCompare(right.name, locale))
  ), [editingId, form.protocol, groups, locale])

  const seriesOptions = useMemo(() => {
    const availableKeys = new Set<ModelSeriesKey>()
    for (const group of groupRows) {
      availableKeys.add(getSeriesKey(group))
    }

    const available = MODEL_SERIES_PRESETS.filter((item) => item.key !== 'other' && availableKeys.has(item.key))
    if (availableKeys.has('other')) {
      const other = MODEL_SERIES_PRESETS.find((item) => item.key === 'other')
      if (other) {
        available.push(other)
      }
    }

    return [{
      key: 'all' as const,
      zh: '全部',
      en: 'All',
      sampleModel: 'all',
    }, ...available]
  }, [groupRows])

  const effectiveSelectedSeries = seriesOptions.some((item) => item.key === selectedSeries)
    ? selectedSeries
    : 'all'

  const visibleGroups = useMemo<GroupRow[]>(() => {
    const keyword = search.trim().toLowerCase()
    const filtered = groupRows.filter((group) => {
      if (effectiveSelectedSeries !== 'all' && getSeriesKey(group) !== effectiveSelectedSeries) return false
      if (protocolFilter !== 'all' && group.protocol !== protocolFilter) return false
      if (strategyFilter !== 'all' && group.strategy !== strategyFilter) return false
      if (!keyword) return true
      const haystack = [
        group.name,
        group.channel_summary,
        ...group.channel_names,
        ...group.items.map((item) => item.model_name),
      ].join(' ').toLowerCase()
      return haystack.includes(keyword)
    })

    return [...filtered].sort((left, right) => {
      if (sortBy === 'name-asc') return left.name.localeCompare(right.name, locale)
      if (sortBy === 'name-desc') return right.name.localeCompare(left.name, locale)
      if (sortBy === 'enabled-desc') return right.enabled_member_count - left.enabled_member_count || left.name.localeCompare(right.name, locale)
      return right.member_count - left.member_count || left.name.localeCompare(right.name, locale)
    })
  }, [effectiveSelectedSeries, groupRows, locale, protocolFilter, search, sortBy, strategyFilter])
  const activeFilterCount = [
    effectiveSelectedSeries !== 'all',
    Boolean(search.trim()),
    protocolFilter !== 'all',
    strategyFilter !== 'all',
  ].filter(Boolean).length

  const filteredCandidates = useMemo(() => {
    return (candidateResponse?.candidates ?? []).filter((item) => {
      const channel = channelMap.get(item.channel_id)
      const channelName = channel?.name || item.channel_name
      const endpoint = channelEndpoint(channel)
      return matchesCandidateSearch(
        `${item.model_name} ${channelName} ${item.credential_name} ${endpoint}`,
        candidateSearch,
      )
    })
  }, [candidateResponse, candidateSearch, channelMap])

  const groupedCandidates = useMemo(() => {
    const groupsByChannel = new Map<string, CandidateChannel>()

    for (const item of filteredCandidates) {
      const channel = channelMap.get(item.channel_id)
      const channelName = channel?.name || item.channel_name
      const existing = groupsByChannel.get(item.channel_id)
      if (existing) {
        const existingCredential = existing.credentials.find((credential) => credential.credential_id === item.credential_id)
        if (existingCredential) {
          existingCredential.items.push(item)
        } else {
          existing.credentials.push({
            credential_id: item.credential_id,
            credential_name: item.credential_name,
            items: [item],
          })
        }
      } else {
        groupsByChannel.set(item.channel_id, {
          channel_id: item.channel_id,
          channel_name: channelName,
          credentials: [{ credential_id: item.credential_id, credential_name: item.credential_name, items: [item] }],
        })
      }
    }

    return Array.from(groupsByChannel.values()).sort((a, b) => a.channel_name.localeCompare(b.channel_name))
  }, [channelMap, filteredCandidates])

  const visibleSelectedMembers = useMemo(() => {
    if (!showEnabledOnly) {
      return form.items.map((item, index) => ({ item, index }))
    }
    return form.items.flatMap((item, index) => (item.enabled ? [{ item, index }] : []))
  }, [form.items, showEnabledOnly])

  useEffect(() => {
    if (!dialogOpen) {
      setCandidateSearch('')
      setExpandedChannels([])
      setDraggingIndex(null)
    }
  }, [dialogOpen])

  useEffect(() => {
    if (!groupedCandidates.length) {
      setExpandedChannels([])
      return
    }
    setExpandedChannels((current) => {
      const available = new Set(groupedCandidates.map((item) => item.channel_id))
      const filtered = current.filter((item) => available.has(item))
      if (filtered.length) {
        return filtered
      }
      return [groupedCandidates[0].channel_id]
    })
  }, [groupedCandidates])

  async function invalidateGroupData() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['groups'] }),
      queryClient.invalidateQueries({ queryKey: ['sites'] }),
      queryClient.invalidateQueries({ queryKey: ['group-candidates'] }),
    ])
  }

  function openCreate() {
    setEditingId(null)
    setForm(emptyForm)
    setDialogOpen(true)
  }

  function openEdit(item: ModelGroup) {
    setEditingId(item.id)
    setForm(toForm(item))
    setDialogOpen(true)
  }

  async function saveGroup(payload: FormState, groupId: string | null) {
    const savedGroup = await apiRequest<ModelGroup>(groupId ? '/admin/model-groups/' + groupId : '/admin/model-groups', {
      method: groupId ? 'PUT' : 'POST',
      body: JSON.stringify(toPayload(payload)),
    })
    await invalidateGroupData()
    return savedGroup
  }

  async function saveGroupPrice(groupName: string, payload: {
    input_price_per_million: number
    output_price_per_million: number
    cache_read_price_per_million: number
    cache_write_price_per_million: number
  }) {
    await apiRequest('/admin/model-prices/' + encodeURIComponent(groupName), {
      method: 'PUT',
      body: JSON.stringify({
        model_key: groupName,
        display_name: groupName,
        ...payload,
      }),
    })
    await queryClient.invalidateQueries({ queryKey: ['groups'] })
  }

  function parsePriceForm(payload: FormState) {
    const input = Number(payload.input_price_per_million)
    const output = Number(payload.output_price_per_million)
    const cacheRead = Number(payload.cache_read_price_per_million)
    const cacheWrite = Number(payload.cache_write_price_per_million)

    if (
      !Number.isFinite(input) || input < 0 ||
      !Number.isFinite(output) || output < 0 ||
      !Number.isFinite(cacheRead) || cacheRead < 0 ||
      !Number.isFinite(cacheWrite) || cacheWrite < 0
    ) {
      throw new Error(locale === 'zh-CN' ? '价格必须是大于等于 0 的数字' : 'Prices must be numbers greater than or equal to 0')
    }

    return {
      input_price_per_million: input,
      output_price_per_million: output,
      cache_read_price_per_million: cacheRead,
      cache_write_price_per_million: cacheWrite,
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try {
      const savedGroup = await saveGroup(form, editingId)
      if (!savedGroup.route_group_id) {
        const pricePayload = parsePriceForm(form)
        await saveGroupPrice(savedGroup.name, pricePayload)
      }
      toast.success(editingId
        ? (locale === 'zh-CN' ? '模型组已更新' : 'Group updated')
        : (locale === 'zh-CN' ? '模型组已创建' : 'Group created'))
      setDialogOpen(false)
      setEditingId(null)
      setForm(emptyForm)
    } catch (e) {
      const message = e instanceof ApiError
        ? e.message
        : e instanceof Error
          ? e.message
          : (locale === 'zh-CN' ? '保存模型组失败' : 'Failed to save group')
      toast.error(message)
    }
  }

  async function syncPrices() {
    setSyncingPrices(true)
    try {
      await apiRequest('/admin/model-price-sync-jobs', { method: 'POST' })
      await queryClient.invalidateQueries({ queryKey: ['groups'] })
      toast.success(locale === 'zh-CN' ? '模型价格已同步' : 'Model prices synced')
    } catch (e) {
      const message = e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '同步模型价格失败' : 'Failed to sync model prices')
      toast.error(message)
    } finally {
      setSyncingPrices(false)
    }
  }

  async function remove(item: ModelGroup) {
    setBusyId(item.id)
    try {
      await apiRequest<void>('/admin/model-groups/' + item.id, { method: 'DELETE' })
      setDeleteTarget(null)
      await invalidateGroupData()
      toast.success(locale === 'zh-CN' ? '模型组已删除' : 'Group deleted')
    } catch (e) {
      const message = e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除模型组失败' : 'Failed to delete group')
      toast.error(message)
    } finally {
      setBusyId(null)
    }
  }

  function addItem(item: ModelGroupCandidateItem) {
    const key = itemKey(item)
    setForm((current) => {
      if (current.items.some((member) => itemKey(member) === key)) {
        return current
      }
      return {
        ...current,
        items: [...current.items, { channel_id: item.channel_id, channel_name: item.channel_name, credential_id: item.credential_id, credential_name: item.credential_name, model_name: item.model_name, enabled: true }],
      }
    })
  }

  function removeItem(index: number) {
    setForm((current) => ({
      ...current,
      items: current.items.filter((_, itemIndex) => itemIndex !== index),
    }))
  }

  function moveItem(fromIndex: number, toIndex: number) {
    setForm((current) => {
      const nextItems = moveItems(current.items, fromIndex, toIndex)
      if (nextItems === current.items) {
        return current
      }
      return { ...current, items: nextItems }
    })
  }

  async function updateGroupPartial(group: ModelGroup, updates: Partial<FormState>) {
    setBusyId(group.id)
    try {
      await saveGroup({ ...toForm(group), ...updates }, group.id)
      return true
    } catch (e) {
      const message = e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '更新模型组失败' : 'Failed to update group')
      toast.error(message)
      return false
    } finally {
      setBusyId(null)
    }
  }

  async function reorderGroupItems(group: GroupRow, fromIndex: number, toIndex: number) {
    if (group.is_route_group || fromIndex === toIndex || busyId === group.id) {
      return
    }
    const nextItems = moveItems(toForm(group).items, fromIndex, toIndex)
    if (nextItems === toForm(group).items) {
      return
    }
    await updateGroupPartial(group, { items: nextItems })
  }

  async function changeStrategy(group: GroupRow, strategy: RoutingStrategy) {
    if (group.is_route_group || busyId === group.id || group.strategy === strategy) {
      return
    }
    const updated = await updateGroupPartial(group, { strategy })
    if (updated) {
      toast.success(locale === 'zh-CN' ? '策略已更新' : 'Strategy updated')
    }
  }

  async function toggleGroupEnabled(group: GroupRow, enabled: boolean) {
    if (group.is_route_group || !group.items.length || busyId === group.id || isGroupEnabled(group) === enabled) {
      return
    }
    const nextItems = toForm(group).items.map((item) => ({ ...item, enabled }))
    const updated = await updateGroupPartial(group, { items: nextItems })
    if (updated) {
      toast.success(enabled
        ? (locale === 'zh-CN' ? '模型组已启动' : 'Group enabled')
        : (locale === 'zh-CN' ? '模型组已停止' : 'Group disabled'))
    }
  }

  async function removeGroupItem(group: GroupRow, index: number) {
    if (group.is_route_group || busyId === group.id) {
      return
    }
    const nextItems = toForm(group).items.filter((_, itemIndex) => itemIndex !== index)
    const updated = await updateGroupPartial(group, { items: nextItems })
    if (updated) {
      toast.success(locale === 'zh-CN' ? '成员已删除' : 'Member removed')
    }
  }

  function toggleChannel(channelId: string) {
    setExpandedChannels((current) => current.includes(channelId) ? current.filter((item) => item !== channelId) : [...current, channelId])
  }

  function addMatchedItems() {
    if (!filteredCandidates.length) {
      return
    }
    setForm((current) => {
      const existing = new Set(current.items.map((item) => itemKey(item)))
      const additions = filteredCandidates
        .filter((item) => !existing.has(itemKey(item)))
        .map((item) => ({
          channel_id: item.channel_id,
          channel_name: item.channel_name,
          credential_id: item.credential_id,
          credential_name: item.credential_name,
          model_name: item.model_name,
          enabled: true,
        }))
      if (!additions.length) {
        return current
      }
      return { ...current, items: [...current.items, ...additions] }
    })
  }

  function changeProtocol(protocol: ProtocolKind) {
    setForm((current) => {
      if (current.protocol === protocol) {
        return current
      }
      return {
        ...current,
        protocol,
        route_group_id: '',
        items: [],
      }
    })
    setExpandedChannels([])
  }

  function changeRouteTarget(routeGroupId: string) {
    setForm((current) => ({
      ...current,
      route_group_id: routeGroupId,
    }))
    setExpandedChannels([])
  }

  function setAllMembersEnabled(enabled: boolean) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item) => ({ ...item, enabled })),
    }))
  }

  function resetFilters() {
    setSelectedSeries('all')
    setSearch('')
    setProtocolFilter('all')
    setStrategyFilter('all')
    setSortBy('members-desc')
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-foreground">{locale === 'zh-CN' ? '模型组' : 'Groups'}</h1>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => void syncPrices()} disabled={syncingPrices}>
            <RefreshCcw data-icon="inline-start" className={syncingPrices ? 'animate-spin' : ''} />
            {syncingPrices
              ? (locale === 'zh-CN' ? '同步中...' : 'Syncing...')
              : (locale === 'zh-CN' ? '同步价格' : 'Sync prices')}
          </Button>
          <Button className="rounded-full" size="icon-sm" type="button" onClick={openCreate}>
            <Plus size={18} />
          </Button>
        </div>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.7fr)_320px]">
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
              onChange={(event) => setSelectedSeries(event.target.value as SelectedSeries)}
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
                  onClick={() => setSelectedSeries(option.key)}
                />
              ))}
            </div>
          </div>

          <Card className="overflow-hidden py-0 xl:min-h-[calc(100dvh-18rem)]">
            <CardContent className="px-3 py-3 xl:max-h-[calc(100dvh-18rem)] xl:overflow-y-auto">
              {isLoading ? (
                <div className="px-2 py-6 text-sm text-muted-foreground">{locale === 'zh-CN' ? '正在加载模型组...' : 'Loading groups...'}</div>
              ) : visibleGroups.length ? (
                <ItemGroup className="gap-3">
                  {visibleGroups.map((group) => {
                    const GroupAvatar = getModelGroupAvatar(group.name)
                    return (
                      <Item
                        key={group.id}
                        variant="outline"
                        role="button"
                        tabIndex={0}
                        className="items-start gap-3 rounded-2xl border-border/80 bg-background px-4 py-4 shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer"
                        onClick={() => openEdit(group)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            openEdit(group)
                          }
                        }}
                      >
                        <ItemMedia variant="icon" className="mt-0.5 hidden size-11 self-start rounded-xl bg-muted/40 sm:flex">
                          <GroupAvatar size={30} />
                        </ItemMedia>
                        <ItemContent className="min-w-0">
                          <div className="flex flex-col gap-1.5">
                            <div className="flex flex-wrap items-center gap-2">
                              <ItemTitle className="truncate text-base">{group.name}</ItemTitle>
                              <Badge variant="outline" className={cn('px-2.5 py-0.5', protocolBadgeClassName(group.protocol))}>
                                {protocolLabel(group.protocol, locale)}
                              </Badge>
                              {group.is_route_group ? (
                                <Badge variant="outline" className="px-2.5 py-0.5">
                                  {locale === 'zh-CN' ? '路由组' : 'Route group'}
                                </Badge>
                              ) : null}
                            </div>
                            {group.is_route_group ? (
                              <ItemDescription className="text-sm">
                                {`${group.name} -> ${group.route_group_name || group.route_group_id || 'n/a'}`}
                              </ItemDescription>
                            ) : (
                              <CompactPriceSummary
                                locale={locale}
                                inputPrice={group.input_price_per_million}
                                outputPrice={group.output_price_per_million}
                                cacheReadPrice={group.cache_read_price_per_million}
                                cacheWritePrice={group.cache_write_price_per_million}
                              />
                            )}
                          </div>
                          {!group.is_route_group ? (
                            <ItemFooter
                              className="mt-3 flex flex-wrap items-center gap-2.5"
                              onClick={(event) => event.stopPropagation()}
                              onKeyDown={(event) => event.stopPropagation()}
                            >
                              <StrategyToggle
                                value={group.strategy}
                                locale={locale}
                                disabled={busyId === group.id}
                                size="sm"
                                className="w-fit max-w-full"
                                onChange={(value) => void changeStrategy(group, value)}
                              />
                            </ItemFooter>
                          ) : null}
                          <div
                            className="mt-3 flex flex-wrap items-center gap-2"
                            onClick={(event) => event.stopPropagation()}
                            onKeyDown={(event) => event.stopPropagation()}
                          >
                            {group.is_route_group ? (
                              <Badge variant="outline" className="px-3 py-1.5">
                                {group.route_group_name || group.route_group_id || 'n/a'}
                              </Badge>
                            ) : group.items.length ? group.items.map((item, index) => {
                              const channelName = item.channel_name || channelMap.get(item.channel_id)?.name || item.channel_id
                              return (
                                <div
                                  key={`${itemKey(item)}::${index}`}
                                  className={cn(
                                    'flex min-w-0 max-w-full items-center rounded-full border bg-background',
                                    !item.enabled && 'opacity-55',
                                    cardDragging?.groupId === group.id && cardDragging.index === index && 'opacity-60'
                                  )}
                                  title={`${channelName} · ${item.model_name}`}
                                >
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    draggable={busyId !== group.id}
                                    className="h-auto min-w-0 max-w-full rounded-full rounded-r-none border-0 px-3 py-1.5 cursor-grab active:cursor-grabbing"
                                    onDragStart={() => setCardDragging({ groupId: group.id, index })}
                                    onDragOver={(event) => event.preventDefault()}
                                    onDrop={() => {
                                      if (!cardDragging || cardDragging.groupId !== group.id) return
                                      void reorderGroupItems(group, cardDragging.index, index)
                                    }}
                                    onDragEnd={() => setCardDragging(null)}
                                  >
                                    <GripVertical data-icon="inline-start" />
                                    <span className="min-w-0 truncate">{item.model_name}</span>
                                    <span className="min-w-0 truncate text-muted-foreground">· {channelName}</span>
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon-xs"
                                    className="mr-1 shrink-0 rounded-full text-muted-foreground hover:text-destructive"
                                    disabled={busyId === group.id}
                                    onClick={() => void removeGroupItem(group, index)}
                                  >
                                    <X />
                                  </Button>
                                </div>
                              )
                            }) : (
                              <ItemDescription className="text-sm">
                                {locale === 'zh-CN' ? '暂无成员' : 'No members'}
                              </ItemDescription>
                            )}
                          </div>
                        </ItemContent>
                        <ItemActions
                          className="basis-full flex-wrap justify-end self-start sm:ml-auto sm:basis-auto sm:shrink-0"
                          onClick={(event) => event.stopPropagation()}
                          onKeyDown={(event) => event.stopPropagation()}
                        >
                          <SwitchButton
                            checked={isGroupEnabled(group)}
                            disabled={group.is_route_group || busyId === group.id || !group.items.length}
                            onChange={(checked) => void toggleGroupEnabled(group, checked)}
                          />
                          <Button type="button" variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteTarget(group)}>
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
                  {effectiveSelectedSeries !== 'all' || search.trim() || protocolFilter !== 'all' || strategyFilter !== 'all'
                    ? (locale === 'zh-CN' ? '没有匹配的模型组。' : 'No matching groups.')
                    : (locale === 'zh-CN' ? '当前还没有模型组。' : 'No groups yet.')}
                </div>
              )}
            </CardContent>
          </Card>
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
                <Button type="button" variant="ghost" size="sm" onClick={resetFilters} disabled={!activeFilterCount && sortBy === 'members-desc'}>
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
                      value={search}
                      onChange={setSearch}
                      onClear={() => setSearch('')}
                      placeholder={locale === 'zh-CN' ? '模型组 / 渠道 / 模型' : 'Group / channel / model'}
                      className="max-w-none"
                    />
                  </Field>

                  <Field>
                    <FieldLabel>{locale === 'zh-CN' ? '协议' : 'Protocol'}</FieldLabel>
                    <NativeSelect value={protocolFilter} className={selectClassName()} onChange={(event) => setProtocolFilter(event.target.value as 'all' | ProtocolKind)}>
                      <NativeSelectOption value="all">{locale === 'zh-CN' ? '全部协议' : 'All protocols'}</NativeSelectOption>
                      {protocolOptions(locale).map((option) => <NativeSelectOption key={option.value} value={option.value}>{option.label}</NativeSelectOption>)}
                    </NativeSelect>
                  </Field>

                  <Field>
                    <FieldLabel>{locale === 'zh-CN' ? '策略' : 'Strategy'}</FieldLabel>
                    <ToggleGroup
                      type="single"
                      value={strategyFilter}
                      onValueChange={(value) => {
                        if (value) {
                          setStrategyFilter(value as 'all' | RoutingStrategy)
                        }
                      }}
                      variant="outline"
                      size="default"
                      spacing={1}
                      className="grid w-full grid-cols-3"
                    >
                      <ToggleGroupItem value="all" className="w-full truncate px-1.5">{locale === 'zh-CN' ? '全部' : 'All'}</ToggleGroupItem>
                      <ToggleGroupItem value="round_robin" className="w-full truncate px-1.5">{locale === 'zh-CN' ? '轮询' : 'Round Robin'}</ToggleGroupItem>
                      <ToggleGroupItem value="failover" className="w-full truncate px-1.5">{locale === 'zh-CN' ? '故障转移' : 'Failover'}</ToggleGroupItem>
                    </ToggleGroup>
                  </Field>

                  <Field>
                    <FieldLabel>{locale === 'zh-CN' ? '排序' : 'Sort'}</FieldLabel>
                    <NativeSelect value={sortBy} className={selectClassName()} onChange={(event) => setSortBy(event.target.value as GroupSort)}>
                      <NativeSelectOption value="members-desc">{locale === 'zh-CN' ? '成员优先' : 'Members first'}</NativeSelectOption>
                      <NativeSelectOption value="enabled-desc">{locale === 'zh-CN' ? '启用优先' : 'Enabled first'}</NativeSelectOption>
                      <NativeSelectOption value="name-asc">{locale === 'zh-CN' ? '名称 A-Z' : 'Name A-Z'}</NativeSelectOption>
                      <NativeSelectOption value="name-desc">{locale === 'zh-CN' ? '名称 Z-A' : 'Name Z-A'}</NativeSelectOption>
                    </NativeSelect>
                  </Field>
                </FieldGroup>
              </FieldSet>
            </div>
          </div>
        </aside>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent className="h-[92dvh] max-w-6xl sm:h-[88vh]" title={editingId ? (locale === 'zh-CN' ? '编辑模型组' : 'Edit group') : (locale === 'zh-CN' ? '新建模型组' : 'Create group')}>
          <form className="flex flex-col gap-4 pr-1" onSubmit={submit}>
            <div className="flex flex-col gap-4">
              <section className="grid gap-4">
                <div className="text-base font-semibold text-foreground">{locale === 'zh-CN' ? '基本信息' : 'Group settings'}</div>
                <FieldGroup className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <Field>
                    <FieldLabel htmlFor="group-protocol">{locale === 'zh-CN' ? '协议' : 'Protocol'}</FieldLabel>
                    <NativeSelect id="group-protocol" className={selectClassName()} value={form.protocol} onChange={(e) => changeProtocol(e.target.value as ProtocolKind)}>
                      {protocolOptions(locale).map((option) => <NativeSelectOption key={option.value} value={option.value}>{option.label}</NativeSelectOption>)}
                    </NativeSelect>
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="group-name">{locale === 'zh-CN' ? '模型组名称' : 'Group name'}</FieldLabel>
                    <Input id="group-name" placeholder={locale === 'zh-CN' ? '例如 claude-sonnet-4-6' : 'For example claude-sonnet-4-6'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="group-route-target">{locale === 'zh-CN' ? '路由目标模型组' : 'Route target group'}</FieldLabel>
                    <NativeSelect id="group-route-target" className={selectClassName()} value={form.route_group_id} onChange={(event) => changeRouteTarget(event.target.value)}>
                      <NativeSelectOption value="">{locale === 'zh-CN' ? '不启用模型组路由' : 'No group routing'}</NativeSelectOption>
                      {routeTargetOptions.map((group) => <NativeSelectOption key={group.id} value={group.id}>{group.name}</NativeSelectOption>)}
                    </NativeSelect>
                  </Field>
                  <Field>
                    <FieldLabel>{locale === 'zh-CN' ? '模型组策略' : 'Group strategy'}</FieldLabel>
                    <StrategyToggle value={form.strategy} locale={locale} disabled={Boolean(form.route_group_id)} onChange={(value) => setForm((current) => ({ ...current, strategy: value }))} />
                  </Field>
                </FieldGroup>
              </section>

              {!form.route_group_id ? (
                <>
                  <Separator />

                  <section className="grid gap-4">
                    <div className="text-base font-semibold text-foreground">{locale === 'zh-CN' ? '价格' : 'Pricing'}</div>
                    <div className="grid gap-3 xl:grid-cols-2">
                      <EditablePriceRow
                        locale={locale}
                        primaryLabel="input"
                        primaryValue={form.input_price_per_million}
                        secondaryLabel="cache_read"
                        secondaryValue={form.cache_read_price_per_million}
                        onPrimaryChange={(value) => setForm((current) => ({ ...current, input_price_per_million: value }))}
                        onSecondaryChange={(value) => setForm((current) => ({ ...current, cache_read_price_per_million: value }))}
                      />
                      <EditablePriceRow
                        locale={locale}
                        primaryLabel="output"
                        primaryValue={form.output_price_per_million}
                        secondaryLabel="cache_write"
                        secondaryValue={form.cache_write_price_per_million}
                        onPrimaryChange={(value) => setForm((current) => ({ ...current, output_price_per_million: value }))}
                        onSecondaryChange={(value) => setForm((current) => ({ ...current, cache_write_price_per_million: value }))}
                      />
                    </div>
                  </section>

                  <Separator />

                  <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
                  <section className={panelClassName('flex flex-col')}>
                <div className="grid gap-3 px-2 py-1 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                  <div className="flex min-w-0 items-center gap-2 rounded-md border bg-background px-3">
                    <Search size={14} className="text-muted-foreground" />
                    <Input className="min-w-0 flex-1 border-0 bg-transparent px-0 py-0 text-sm shadow-none focus-visible:ring-0" value={candidateSearch} onChange={(e) => setCandidateSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索模型或 /正则/' : 'Search models or /regex/'} />
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Button type="button" variant="outline" onClick={addMatchedItems} disabled={!filteredCandidates.length}>
                      <Sparkles size={13} />
                      {locale === 'zh-CN' ? `加入当前筛选 ${filteredCandidates.length}` : `Add filtered ${filteredCandidates.length}`}
                    </Button>
                    <Button type="button" variant="outline" onClick={() => void refetchCandidates()} disabled={isFetchingCandidates}>
                      <RefreshCcw size={13} />
                      {locale === 'zh-CN' ? '刷新列表' : 'Refresh'}
                    </Button>
                  </div>
                </div>

                <div className="px-2 pb-2">
                  <div className="flex flex-col gap-2">
                    {groupedCandidates.map((channel) => {
                      const currentChannel = channelMap.get(channel.channel_id)
                      const isOpen = expandedChannels.includes(channel.channel_id)
                      const endpoint = channelEndpoint(currentChannel)
                      return (
                        <div key={channel.channel_id} className="border-b pb-2 last:border-b-0 last:pb-0">
                          <Button type="button" variant="ghost" className="h-auto w-full justify-start gap-3 rounded-none px-3 py-3 text-left hover:bg-muted" onClick={() => toggleChannel(channel.channel_id)}>
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-sm font-medium text-foreground">{channel.channel_name}</div>
                              <div className="mt-1 truncate text-xs text-muted-foreground">{endpoint}</div>
                            </div>
                            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{channel.credentials.reduce((total, credential) => total + credential.items.length, 0)}</span>
                            <ChevronDown size={15} className={cn('text-muted-foreground transition-transform', isOpen && 'rotate-180')} />
                          </Button>
                          {isOpen ? (
                            <div className="flex flex-col gap-2 px-3 py-2.5">
                              <Separator />
                              {channel.credentials.map((credential) => (
                                <div key={`${channel.channel_id}-${credential.credential_id}`} className="flex flex-col gap-1.5 py-1.5">
                                  <div className="px-1 text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground">{credential.credential_name || (locale === 'zh-CN' ? '未命名 Key' : 'Unnamed key')}</div>
                                  {credential.items.map((item) => (
                                    <CandidateRow key={`${item.channel_id}-${item.credential_id}-${item.model_name}`} item={item} active={form.items.some((member) => itemKey(member) === itemKey(item))} onClick={() => addItem(item)} />
                                  ))}
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      )
                    })}
                    {!groupedCandidates.length ? <p className="px-1 py-6 text-center text-sm text-muted-foreground">{locale === 'zh-CN' ? '暂无可选模型' : 'No candidates found'}</p> : null}
                  </div>
                </div>
              </section>

              <section className={panelClassName('flex flex-col')}>
                <div className="flex flex-col items-start justify-between gap-3 px-2 py-1 sm:flex-row sm:items-center">
                  <div className="text-sm font-medium text-foreground">{locale === 'zh-CN' ? '已选模型' : 'Selected models'}</div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Button type="button" variant="outline" className="text-muted-foreground" onClick={() => setAllMembersEnabled(true)}>{locale === 'zh-CN' ? '全开' : 'Enable all'}</Button>
                    <Button type="button" variant="outline" className="text-muted-foreground" onClick={() => setAllMembersEnabled(false)}>{locale === 'zh-CN' ? '全关' : 'Disable all'}</Button>
                    <Button type="button" variant={showEnabledOnly ? 'default' : 'outline'} className={cn(!showEnabledOnly && 'text-muted-foreground')} onClick={() => setShowEnabledOnly((current) => !current)}>{locale === 'zh-CN' ? '仅看启用' : 'Enabled only'}</Button>
                    <span className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">{visibleSelectedMembers.length}/{form.items.length}</span>
                  </div>
                </div>
                <div className="px-2 pb-2 pt-1">
                  <div className="flex flex-col gap-1.5">
                    {visibleSelectedMembers.length ? visibleSelectedMembers.map(({ item, index }) => (
                      <SelectedMemberRow
                        key={`${itemKey(item)}::${index}`}
                        item={item}
                        index={index}
                        dragging={draggingIndex === index}
                        busy={false}
                        onToggle={() => setForm((current) => ({
                          ...current,
                          items: current.items.map((member, memberIndex) => memberIndex === index ? { ...member, enabled: !member.enabled } : member),
                        }))}
                        onRemove={() => removeItem(index)}
                        onDragStart={() => setDraggingIndex(index)}
                        onDragEnter={() => {
                          if (draggingIndex === null || draggingIndex === index) return
                          moveItem(draggingIndex, index)
                          setDraggingIndex(index)
                        }}
                        onDragEnd={() => setDraggingIndex(null)}
                      />
                    )) : <p className="px-1 py-6 text-center text-sm text-muted-foreground">{locale === 'zh-CN' ? '当前筛选下没有成员' : 'No members under current filter'}</p>}
                  </div>
                </div>
              </section>
            </div>
            </>
              ) : null}
            </div>

            <div className="sticky bottom-0 z-10 -mx-1 mt-4 shrink-0 border-t bg-background/95 px-1 pt-4 pb-1 backdrop-blur supports-[backdrop-filter]:bg-background/85">
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
                <Button variant="outline" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</Button>
                <Button type="submit">{editingId ? (locale === 'zh-CN' ? '保存模型组' : 'Save group') : (locale === 'zh-CN' ? '创建模型组' : 'Create group')}</Button>
              </div>
            </div>
          </form>
        </AppDialogContent>
      </Dialog>

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除模型组' : 'Delete group'} description={locale === 'zh-CN' ? '删除后，该模型组名称将不再参与路由匹配。' : 'This group will no longer participate in routing.'}>
          <div className="grid gap-5 overflow-y-auto pr-1">
            <div className="rounded-md border bg-muted/30 p-4"><strong>{deleteTarget?.name}</strong></div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button variant="outline" type="button" onClick={() => setDeleteTarget(null)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</Button>
              <Button variant="destructive" type="button" onClick={() => deleteTarget && void remove(deleteTarget)} disabled={busyId === deleteTarget?.id}>{busyId === deleteTarget?.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '确认删除' : 'Delete')}</Button>
            </div>
          </div>
        </AppDialogContent>
      </Dialog>
    </section>
  )
}
