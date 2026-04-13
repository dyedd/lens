"use client"

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, GripVertical, Pencil, Plus, RefreshCcw, Search, Sparkles, Trash2, X } from 'lucide-react'
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
import { getModelGroupAvatar } from '@/lib/model-icons'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
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
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
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
  match_regex: string
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

const emptyForm: FormState = {
  name: '',
  protocol: 'openai_chat',
  strategy: 'round_robin',
  match_regex: '',
  items: [],
}

function normalizeMatchValue(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, '')
}

function matchesCandidate(modelName: string, groupName: string, matchRegex: string) {
  const regexValue = matchRegex.trim()
  if (regexValue) {
    try {
      return new RegExp(regexValue, 'i').test(modelName)
    } catch {
      return false
    }
  }

  const normalizedGroupName = normalizeMatchValue(groupName)
  if (!normalizedGroupName) {
    return false
  }
  return normalizeMatchValue(modelName).includes(normalizedGroupName)
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

function protocolOptions(locale: 'zh-CN' | 'en-US') {
  return (Object.keys(protocolLabels) as ProtocolKind[]).map((value) => ({
    value,
    label: protocolLabel(value, locale),
  }))
}

function panelClassName(extra = '') {
  return cn('rounded-lg bg-muted/10', extra)
}

function selectClassName() {
  return 'w-full [&_select]:border-border [&_select]:bg-background [&_select]:text-sm [&_select]:text-foreground'
}

function itemKey(item: Pick<FormItem, 'channel_id' | 'credential_id' | 'model_name'>) {
  return `${item.channel_id}::${item.credential_id}::${item.model_name}`
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
    match_regex: group.match_regex,
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
    match_regex: form.match_regex.trim(),
    items: form.items.map((item) => ({ channel_id: item.channel_id, credential_id: item.credential_id, model_name: item.model_name, enabled: item.enabled })),
  }
}

function SwitchButton({ checked, disabled, onChange }: { checked: boolean; disabled?: boolean; onChange: (checked: boolean) => void }) {
  return <Switch checked={checked} disabled={disabled} onCheckedChange={onChange} />
}

function StrategyToggle({
  value,
  locale,
  disabled = false,
  onChange,
}: {
  value: RoutingStrategy
  locale: 'zh-CN' | 'en-US'
  disabled?: boolean
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
      size="default"
      spacing={1}
      className="flex-wrap"
    >
      {strategyOptions.map((option) => (
        <ToggleGroupItem key={option.value} value={option.value} disabled={disabled}>
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
        'flex items-center gap-2 border-b px-2.5 py-2 transition last:border-b-0',
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

export function GroupsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const [search, setSearch] = useState('')
  const [candidateSearch, setCandidateSearch] = useState('')
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null)
  const [detailTarget, setDetailTarget] = useState<ModelGroup | null>(null)
  const [expandedChannels, setExpandedChannels] = useState<string[]>([])
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null)
  const [showEnabledOnly, setShowEnabledOnly] = useState(false)

  const { data: groups, isLoading } = useQuery({ queryKey: ['groups'], queryFn: () => apiRequest<ModelGroup[]>('/admin/model-groups') })
  const { data: sites } = useQuery({ queryKey: ['sites'], queryFn: () => apiRequest<Site[]>('/admin/sites') })
  const candidatePayload: ModelGroupCandidatesPayload = useMemo(() => ({
    exclude_items: form.items.map((item) => ({ channel_id: item.channel_id, credential_id: item.credential_id, model_name: item.model_name, enabled: item.enabled })),
  }), [form])
  const { data: candidateResponse, refetch: refetchCandidates, isFetching: isFetchingCandidates } = useQuery({
    queryKey: ['group-candidates', candidatePayload],
    queryFn: () => apiRequest<ModelGroupCandidatesResponse>('/admin/model-group-candidates', {
      method: 'POST',
      body: JSON.stringify(candidatePayload),
    }),
    enabled: dialogOpen,
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

  const visibleGroups = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) return groups ?? []
    return (groups ?? []).filter((group) => {
      const haystack = [
        group.name,
        ...group.items.map((item) => item.channel_name),
        ...group.items.map((item) => item.model_name),
      ].join(' ').toLowerCase()
      return haystack.includes(keyword)
    })
  }, [groups, search])

  const detailIconMeta = useMemo(() => {
    return detailTarget ? getModelGroupAvatar(detailTarget.name) : null
  }, [detailTarget])
  const DetailAvatar = detailIconMeta


  const groupedCandidates = useMemo(() => {
    const keyword = candidateSearch.trim().toLowerCase()
    const groupsByChannel = new Map<string, CandidateChannel>()

    for (const item of candidateResponse?.candidates ?? []) {
      const channel = channelMap.get(item.channel_id)
      const channelName = channel?.name || item.channel_name
      const endpoint = channelEndpoint(channel)
      const matchItem = !keyword || `${item.model_name} ${channelName} ${item.credential_name} ${endpoint}`.toLowerCase().includes(keyword)
      if (!matchItem) {
        continue
      }
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
  }, [candidateResponse, candidateSearch, channelMap])

  const visibleSelectedItems = useMemo(() => {
    if (!showEnabledOnly) return form.items
    return form.items.filter((item) => item.enabled)
  }, [form.items, showEnabledOnly])

  const matchedCandidates = useMemo(() => {
    return (candidateResponse?.candidates ?? []).filter((item) => matchesCandidate(item.model_name, form.name, form.match_regex))
  }, [candidateResponse, form.name, form.match_regex])

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
    setError('')
    setDialogOpen(true)
  }

  function openEdit(item: ModelGroup) {
    setEditingId(item.id)
    setForm(toForm(item))
    setError('')
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      await saveGroup(form, editingId)
      setDialogOpen(false)
      setEditingId(null)
      setForm(emptyForm)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存模型组失败' : 'Failed to save group'))
    }
  }

  async function remove(item: ModelGroup) {
    setBusyId(item.id)
    setError('')
    try {
      await apiRequest<void>('/admin/model-groups/' + item.id, { method: 'DELETE' })
      setDeleteTarget(null)
      await invalidateGroupData()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除模型组失败' : 'Failed to delete group'))
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
    setError('')
    try {
      const savedGroup = await saveGroup({ ...toForm(group), ...updates }, group.id)
      if (detailTarget?.id === group.id) {
        setDetailTarget(savedGroup)
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '更新模型组失败' : 'Failed to update group'))
    } finally {
      setBusyId(null)
    }
  }

  async function changeStrategy(group: ModelGroup, strategy: RoutingStrategy) {
    if (group.strategy === strategy || busyId === group.id) {
      return
    }
    await updateGroupPartial(group, { strategy })
  }

  async function toggleMember(group: ModelGroup, index: number) {
    const nextItems = toForm(group).items.map((item, itemIndex) => itemIndex === index ? { ...item, enabled: !item.enabled } : item)
    await updateGroupPartial(group, { items: nextItems })
  }

  function toggleChannel(channelId: string) {
    setExpandedChannels((current) => current.includes(channelId) ? current.filter((item) => item !== channelId) : [...current, channelId])
  }

  function addMatchedItems() {
    if (!matchedCandidates.length) {
      return
    }
    setForm((current) => {
      const existing = new Set(current.items.map((item) => itemKey(item)))
      const additions = matchedCandidates
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
        items: [],
      }
    })
    setExpandedChannels([])
  }

  function setAllMembersEnabled(enabled: boolean) {
    setForm((current) => ({
      ...current,
      items: current.items.map((item) => ({ ...item, enabled })),
    }))
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">{locale === 'zh-CN' ? '模型组' : 'Groups'}</h1>
        <div className="flex items-center gap-2">
          <ToolbarSearchInput
            value={search}
            onChange={setSearch}
            onClear={() => setSearch('')}
            placeholder={locale === 'zh-CN' ? '搜索模型组' : 'Search groups'}
          />
          <Button className="rounded-lg" size="icon-sm" type="button" onClick={openCreate}>
            <Plus size={18} />
          </Button>
        </div>
      </div>

      <div className="mt-2">
        {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
        {isLoading ? <p className="mb-4 text-sm text-muted-foreground">{locale === 'zh-CN' ? '正在加载模型组...' : 'Loading groups...'}</p> : null}
      </div>

      {visibleGroups.length ? (
        <div className="rounded-xl border bg-card p-3">
          <ItemGroup className="gap-3">
            {visibleGroups.map((group) => {
              const GroupAvatar = getModelGroupAvatar(group.name)
              const items = group.items.slice().sort((a, b) => a.sort_order - b.sort_order)
              const cardItems = items.map((item) => ({
                channel_id: item.channel_id,
                channel_name: item.channel_name || channelMap.get(item.channel_id)?.name || item.channel_id,
                credential_id: item.credential_id,
                credential_name: item.credential_name,
                model_name: item.model_name,
                enabled: item.enabled,
              }))
              const previewItems = cardItems.slice(0, 3)
              return (
                <Item key={group.id} variant="outline" className="gap-4 px-4 py-4">
                  <ItemMedia variant="icon" className="flex size-11 rounded-xl bg-muted/40">
                    <GroupAvatar size={30} />
                  </ItemMedia>
                  <ItemContent className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <ItemTitle className="truncate">{group.name}</ItemTitle>
                      <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-medium">
                        {protocolLabel(group.protocol, locale)}
                      </Badge>
                      <Badge variant="outline" className="px-2.5 py-0.5 text-xs font-medium">
                        {items.length}
                        {locale === 'zh-CN' ? ' 个成员' : ' members'}
                      </Badge>
                    </div>
                    <ItemDescription className="mt-1">
                      {group.match_regex || (locale === 'zh-CN' ? '未设置匹配规则，默认按模型组名称匹配。' : 'No match regex, matching by group name.')}
                    </ItemDescription>
                    <ItemFooter className="mt-4 flex flex-wrap items-center justify-between gap-3">
                      <StrategyToggle
                        value={group.strategy}
                        locale={locale}
                        disabled={busyId === group.id}
                        onChange={(value) => void changeStrategy(group, value)}
                      />
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {previewItems.map((item, index) => (
                          <Button
                            key={itemKey(item)}
                            type="button"
                            variant="outline"
                            size="sm"
                            className={cn('h-auto rounded-full px-3 py-1.5', !item.enabled && 'opacity-55')}
                            onClick={() => {
                              void toggleMember(group, index)
                            }}
                            disabled={busyId === group.id}
                          >
                            {item.model_name}
                          </Button>
                        ))}
                        {cardItems.length > previewItems.length ? (
                          <Badge variant="outline" className="px-2.5 py-1 text-xs font-medium">
                            +{cardItems.length - previewItems.length}
                          </Badge>
                        ) : null}
                      </div>
                    </ItemFooter>
                  </ItemContent>
                  <ItemActions className="ml-auto self-start">
                    <Button type="button" variant="ghost" size="icon-sm" className="text-muted-foreground" onClick={() => setDetailTarget(group)}>
                      <Search size={15} />
                    </Button>
                    <Button type="button" variant="ghost" size="icon-sm" className="text-muted-foreground" onClick={() => openEdit(group)}><Pencil size={15} /></Button>
                    <Button type="button" variant="ghost" size="icon-sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteTarget(group)}><Trash2 size={15} /></Button>
                  </ItemActions>
                </Item>
              )
            })}
          </ItemGroup>
        </div>
      ) : null}

      {!isLoading && !visibleGroups.length ? (
        <div className="rounded-xl border border-dashed bg-card px-6 py-12 text-center text-sm text-muted-foreground">
          {search.trim()
            ? (locale === 'zh-CN' ? '没有匹配的模型组。' : 'No matching groups.')
            : (locale === 'zh-CN' ? '当前还没有模型组。' : 'No groups yet.')}
        </div>
      ) : null}

      <Dialog open={Boolean(detailTarget)} onOpenChange={(open) => { if (!open) setDetailTarget(null) }}>
        {detailTarget ? (
          <AppDialogContent className="max-w-3xl" title={locale === 'zh-CN' ? '模型组详情' : 'Group detail'}>
            <div className="flex flex-col gap-4 overflow-y-auto pr-1">
              <div className={panelClassName('p-4')}>
                <div className="mb-4 flex items-center gap-3">
                  {DetailAvatar ? <DetailAvatar size={44} /> : null}
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-foreground">{detailTarget.name}</div>
                  </div>
                </div>
                <div className="text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground">{locale === 'zh-CN' ? '基础信息' : 'Overview'}</div>
                <div className="mt-3 grid gap-x-6 gap-y-3 text-sm text-foreground md:grid-cols-2">
                  <div><div className="text-xs text-muted-foreground">{locale === 'zh-CN' ? '名称' : 'Name'}</div><div className="mt-1">{detailTarget.name}</div></div>
                  <div><div className="text-xs text-muted-foreground">{locale === 'zh-CN' ? '协议' : 'Protocol'}</div><div className="mt-1">{protocolLabel(detailTarget.protocol, locale)}</div></div>
                  <div><div className="text-xs text-muted-foreground">{locale === 'zh-CN' ? '策略' : 'Strategy'}</div><div className="mt-1">{strategyOptions.find((item) => item.value === detailTarget.strategy)?.[locale === 'zh-CN' ? 'zh' : 'en']}</div></div>
                  <div><div className="text-xs text-muted-foreground">{locale === 'zh-CN' ? '成员数量' : 'Members'}</div><div className="mt-1">{detailTarget.items.length}</div></div>
                  <div className="md:col-span-2"><div className="text-xs text-muted-foreground">{locale === 'zh-CN' ? '匹配正则' : 'Match regex'}</div><div className="mt-1 break-all">{detailTarget.match_regex || (locale === 'zh-CN' ? '未设置，按名称匹配' : 'Not set, match by name')}</div></div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <Button className="h-11" type="button" onClick={() => openEdit(detailTarget)}>{locale === 'zh-CN' ? '编辑模型组' : 'Edit group'}</Button>
                <Button className="h-11" variant="destructive" type="button" onClick={() => setDeleteTarget(detailTarget)}>{locale === 'zh-CN' ? '删除模型组' : 'Delete group'}</Button>
              </div>
            </div>
          </AppDialogContent>
        ) : null}
      </Dialog>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent className="max-w-6xl" title={editingId ? (locale === 'zh-CN' ? '编辑模型组' : 'Edit group') : (locale === 'zh-CN' ? '新建模型组' : 'Create group')}>
          <form className="flex h-full min-h-0 flex-col overflow-hidden" onSubmit={submit}>
            <div className="hide-scrollbar flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto pr-1" style={{ maxHeight: 'calc(88vh - 210px)' }}>
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
                    <FieldLabel htmlFor="group-match-regex">{locale === 'zh-CN' ? '匹配正则' : 'Match regex'}</FieldLabel>
                    <Input id="group-match-regex" placeholder={locale === 'zh-CN' ? '留空则按模型组名称匹配' : 'Optional, otherwise match by group name'} value={form.match_regex} onChange={(e) => setForm({ ...form, match_regex: e.target.value })} />
                    <FieldDescription>{locale === 'zh-CN' ? '用于自动批量匹配模型，也用于路由匹配。' : 'Used for bulk matching and routing.'}</FieldDescription>
                  </Field>
                  <Field>
                    <FieldLabel>{locale === 'zh-CN' ? '路由策略' : 'Routing strategy'}</FieldLabel>
                    <StrategyToggle value={form.strategy} locale={locale} onChange={(value) => setForm((current) => ({ ...current, strategy: value }))} />
                  </Field>
                </FieldGroup>
              </section>

              <Separator />

              <div className="grid min-h-0 gap-4 overflow-hidden lg:grid-cols-[1.05fr_0.95fr]">
              <section className={panelClassName('flex min-h-0 flex-col overflow-hidden')}>
                <div className="grid gap-3 px-2 py-1 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                  <div className="flex min-w-0 items-center gap-2 rounded-md border bg-background px-3">
                    <Search size={14} className="text-muted-foreground" />
                    <Input className="min-w-0 flex-1 border-0 bg-transparent px-0 py-0 text-sm shadow-none focus-visible:ring-0" value={candidateSearch} onChange={(e) => setCandidateSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索模型' : 'Search models'} />
                  </div>
                  <div className="flex items-center justify-end gap-2">
                    <Button type="button" variant="outline" onClick={addMatchedItems} disabled={!matchedCandidates.length}>
                      <Sparkles size={13} />
                      {locale === 'zh-CN' ? `批量加入 ${matchedCandidates.length}` : `Add matched ${matchedCandidates.length}`}
                    </Button>
                    <Button type="button" variant="outline" onClick={() => void refetchCandidates()} disabled={isFetchingCandidates}>
                      <RefreshCcw size={13} />
                      {locale === 'zh-CN' ? '刷新列表' : 'Refresh'}
                    </Button>
                  </div>
                </div>

                <div className="hide-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-2">
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

              <section className={panelClassName('flex min-h-0 flex-col overflow-hidden')}>
                <div className="flex items-center justify-between px-2 py-1">
                  <div className="text-sm font-medium text-foreground">{locale === 'zh-CN' ? '已选模型' : 'Selected models'}</div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <Button type="button" variant="outline" className="text-muted-foreground" onClick={() => setAllMembersEnabled(true)}>{locale === 'zh-CN' ? '全开' : 'Enable all'}</Button>
                    <Button type="button" variant="outline" className="text-muted-foreground" onClick={() => setAllMembersEnabled(false)}>{locale === 'zh-CN' ? '全关' : 'Disable all'}</Button>
                    <Button type="button" variant={showEnabledOnly ? 'default' : 'outline'} className={cn(!showEnabledOnly && 'text-muted-foreground')} onClick={() => setShowEnabledOnly((current) => !current)}>{locale === 'zh-CN' ? '仅看启用' : 'Enabled only'}</Button>
                    <span className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">{visibleSelectedItems.length}/{form.items.length}</span>
                  </div>
                </div>
                <div className="hide-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-2 pt-1">
                  <div className="flex flex-col gap-1.5">
                    {visibleSelectedItems.length ? visibleSelectedItems.map((item) => {
                      const index = form.items.findIndex((candidate) => itemKey(candidate) === itemKey(item))
                      return (
                      <SelectedMemberRow
                        key={itemKey(item)}
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
                    )}) : <p className="px-1 py-6 text-center text-sm text-muted-foreground">{locale === 'zh-CN' ? '当前筛选下没有成员' : 'No members under current filter'}</p>}
                  </div>
                </div>
              </section>
            </div>
            </div>

            <div className="mt-4 shrink-0 border-t bg-background pt-4">
              {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}
              <div className="flex justify-end gap-3">
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
            <div className="flex justify-end gap-3">
              <Button variant="outline" type="button" onClick={() => setDeleteTarget(null)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</Button>
              <Button variant="destructive" type="button" onClick={() => deleteTarget && void remove(deleteTarget)} disabled={busyId === deleteTarget?.id}>{busyId === deleteTarget?.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '确认删除' : 'Delete')}</Button>
            </div>
          </div>
        </AppDialogContent>
      </Dialog>
    </section>
  )
}
