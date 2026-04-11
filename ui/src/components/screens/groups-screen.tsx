"use client"

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
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
import { cn } from '@/lib/cn'
import { getModelGroupAvatar } from '@/lib/model-icons'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'

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

function inputClassName() {
  return 'h-10 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-[13px] text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function panelClassName(extra = '') {
  return cn('rounded-[24px] border border-[var(--line)] bg-[var(--panel)]', extra)
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
      <span
        className={cn(
          'absolute top-1 h-4 w-4 rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,0.18)] transition-all duration-200',
          checked ? 'right-1' : 'left-1'
        )}
      />
    </button>
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
    <button
      type="button"
      onClick={onClick}
      disabled={active}
      className={cn(
        'flex w-full items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 py-2.5 text-left transition',
        active ? 'cursor-not-allowed opacity-60' : 'hover:bg-[var(--panel-soft)]'
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-medium text-[var(--text)]">{item.model_name}</div>
      </div>
      <span className="shrink-0 text-[var(--muted)]">{active ? <Check size={15} className="text-[var(--accent)]" /> : <Plus size={15} />}</span>
    </button>
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
        'flex items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-2.5 py-2 transition',
        dragging && 'opacity-60 shadow-[var(--shadow-sm)]',
        !item.enabled && 'opacity-55'
      )}
    >
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-[var(--accent-2)] text-[11px] font-semibold text-[var(--accent)]">{index + 1}</span>
      <span className="cursor-grab text-[var(--muted)] active:cursor-grabbing">
        <GripVertical size={14} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-medium text-[var(--text)]">{item.model_name}</div>
        <div className="truncate text-[11px] text-[var(--muted)]">{item.channel_name}{!item.enabled ? ' · 已关闭' : ''}</div>
      </div>
      <SwitchButton checked={item.enabled} disabled={busy} onChange={onToggle} />
      <button type="button" className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-[var(--muted)] transition hover:bg-[rgba(217,111,93,0.08)] hover:text-[var(--danger)]" onClick={onRemove}>
        <X size={13} />
      </button>
    </div>
  )
}

function CardMemberRow({
  item,
  index,
  dragging,
  busy,
  onToggle,
  onDragStart,
  onDrop,
  onDragEnd,
}: {
  item: FormItem
  index: number
  dragging: boolean
  busy: boolean
  onToggle: () => void
  onDragStart: () => void
  onDrop: () => void
  onDragEnd: () => void
}) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault()
        onDrop()
      }}
      onDragEnd={onDragEnd}
      className={cn(
        'flex items-start gap-3 rounded-2xl bg-[var(--panel-soft)] px-3 py-2.5 transition',
        dragging && 'opacity-60 shadow-[var(--shadow-sm)]',
        !item.enabled && 'opacity-55'
      )}
    >
      <span className="mt-0.5 flex h-5 w-5 items-center justify-center rounded-md bg-[rgba(37,99,235,0.12)] text-[11px] text-[var(--accent)]">{index + 1}</span>
      <span className="mt-0.5 cursor-grab text-[var(--muted)] active:cursor-grabbing">
        <GripVertical size={14} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-medium text-[var(--text)]">{item.model_name}</div>
        <div className="mt-1 truncate text-xs text-[var(--muted)]">{item.channel_name}{!item.enabled ? ' · 已关闭' : ''}</div>
      </div>
      <SwitchButton checked={item.enabled} disabled={busy} onChange={onToggle} />
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
  const [cardDraggingKey, setCardDraggingKey] = useState<string | null>(null)
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
      const nextProtocol = channelMap.get(item.channel_id)?.protocol || current.protocol
      return {
        ...current,
        protocol: nextProtocol,
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
      setCardDraggingKey(null)
    }
  }

  async function changeStrategy(group: ModelGroup, strategy: RoutingStrategy) {
    if (group.strategy === strategy || busyId === group.id) {
      return
    }
    await updateGroupPartial(group, { strategy })
  }

  async function reorderCardItems(group: ModelGroup, fromIndex: number, toIndex: number) {
    const orderedItems = toForm(group).items
    const nextItems = moveItems(orderedItems, fromIndex, toIndex)
    if (nextItems === orderedItems) {
      setCardDraggingKey(null)
      return
    }
    await updateGroupPartial(group, { items: nextItems })
  }

  function updateCardDrag(groupId: string, index: number) {
    setCardDraggingKey(`${groupId}:${index}`)
  }

  function resetCardDrag() {
    setCardDraggingKey(null)
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
    <section className="space-y-4">
      {typeof document !== 'undefined' && document.getElementById('header-portal') ? createPortal(
        <div className="flex flex-1 items-center justify-end gap-2">
          <div className="flex h-9 w-full max-w-sm items-center rounded-lg border border-[var(--line)] bg-[var(--panel-strong)] px-3 shadow-sm transition-colors focus-within:border-[var(--accent)]">
            <Search size={15} className="text-[var(--muted)]" />
            <input className="ml-2 h-full min-w-0 flex-1 bg-transparent text-[13px] outline-none" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索模型组' : 'Search groups'} />
            {search ? <button type="button" className="text-[var(--muted)] hover:text-[var(--text)]" onClick={() => setSearch('')}><X size={14} /></button> : null}
          </div>
          <button className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)] text-white shadow-sm transition-colors hover:opacity-90" type="button" onClick={openCreate}>
            <Plus size={18} />
          </button>
        </div>,
        document.getElementById('header-portal')!
      ) : null}

      <div className="mt-2">
        {error ? <p className="text-sm text-[var(--danger)] mb-4">{error}</p> : null}
        {isLoading ? <p className="text-sm text-[var(--muted)] mb-4">{locale === 'zh-CN' ? '正在加载模型组...' : 'Loading groups...'}</p> : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
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
          return (
            <article key={group.id} className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
              <div className="flex items-start justify-between gap-3">
                <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setDetailTarget(group)}>
                  <div className="flex items-center gap-3">
                    <GroupAvatar size={36} />
                    <div className="min-w-0">
                      <div className="truncate text-[15px] font-semibold text-[var(--text)]">{group.name}</div>
                    </div>
                  </div>
                </button>
                <div className="flex items-center gap-1.5">
                  <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--text)]" onClick={() => openEdit(group)}><Pencil size={15} /></button>
                  <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--danger)] transition hover:bg-[rgba(217,111,93,0.08)]" onClick={() => setDeleteTarget(group)}><Trash2 size={15} /></button>
                </div>
              </div>

              <div className="mt-4 flex gap-1">
                {strategyOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    disabled={busyId === group.id}
                    onClick={() => void changeStrategy(group, option.value)}
                    className={cn(
                      'flex-1 rounded-xl px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                      option.value === group.strategy
                        ? 'bg-[var(--accent)] text-white'
                        : 'bg-[var(--panel-soft)] text-[var(--text)] hover:bg-[var(--panel)]'
                    )}
                  >
                    {locale === 'zh-CN' ? option.zh : option.en}
                  </button>
                ))}
              </div>

              <div className={panelClassName('mt-4 p-3')}>
                <button type="button" className="w-full text-left" onClick={() => setDetailTarget(group)}>
                <div className="flex items-center justify-between gap-2 text-xs font-medium uppercase tracking-[0.08em] text-[var(--muted)]">
                  <span>{locale === 'zh-CN' ? '模型成员' : 'Members'}</span>
                  <span>{items.length}</span>
                </div>
                </button>
                <div className="mt-3 space-y-2">
                  {cardItems.length ? cardItems.map((item, index) => (
                    <CardMemberRow
                      key={itemKey(item)}
                      item={item}
                      index={index}
                      dragging={cardDraggingKey === `${group.id}:${index}`}
                      busy={busyId === group.id}
                      onToggle={() => void toggleMember(group, index)}
                      onDragStart={() => updateCardDrag(group.id, index)}
                      onDrop={() => {
                        const prefix = `${group.id}:`
                        if (!cardDraggingKey?.startsWith(prefix)) return
                        const fromIndex = Number.parseInt(cardDraggingKey.slice(prefix.length), 10)
                        if (Number.isNaN(fromIndex) || fromIndex === index) {
                          resetCardDrag()
                          return
                        }
                        void reorderCardItems(group, fromIndex, index)
                      }}
                      onDragEnd={resetCardDrag}
                    />
                  )) : <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '暂无成员' : 'No members'}</p>}
                </div>
              </div>
            </article>
          )
        })}
      </div>

      <Dialog.Root open={Boolean(detailTarget)} onOpenChange={(open) => { if (!open) setDetailTarget(null) }}>
        {detailTarget ? (
          <AppDialogContent className="max-w-3xl" title={locale === 'zh-CN' ? '模型组详情' : 'Group detail'}>
            <div className="space-y-5 overflow-y-auto pr-1">
              <div className={panelClassName('p-5')}>
                <div className="mb-4 flex items-center gap-3">
                  {DetailAvatar ? <DetailAvatar size={44} /> : null}
                  <div className="min-w-0">
                    <div className="truncate text-base font-semibold text-[var(--text)]">{detailTarget.name}</div>
                    <div className="text-xs text-[var(--muted)]">{protocolLabel(detailTarget.protocol, locale)}</div>
                  </div>
                </div>
                <div className="text-xs font-medium uppercase tracking-[0.08em] text-[var(--muted)]">{locale === 'zh-CN' ? '基础信息' : 'Overview'}</div>
                <div className="mt-4 grid gap-x-8 gap-y-4 text-sm text-[var(--text)] md:grid-cols-2">
                  <div><div className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '名称' : 'Name'}</div><div className="mt-1">{detailTarget.name}</div></div>
                  <div><div className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '协议' : 'Protocol'}</div><div className="mt-1">{protocolLabel(detailTarget.protocol, locale)}</div></div>
                  <div><div className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '策略' : 'Strategy'}</div><div className="mt-1">{strategyOptions.find((item) => item.value === detailTarget.strategy)?.[locale === 'zh-CN' ? 'zh' : 'en']}</div></div>
                  <div><div className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '成员数量' : 'Members'}</div><div className="mt-1">{detailTarget.items.length}</div></div>
                  <div className="md:col-span-2"><div className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '匹配正则' : 'Match regex'}</div><div className="mt-1 break-all">{detailTarget.match_regex || (locale === 'zh-CN' ? '未设置，按名称匹配' : 'Not set, match by name')}</div></div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <button className="h-12 rounded-2xl bg-[var(--accent)] text-sm font-medium text-white" type="button" onClick={() => openEdit(detailTarget)}>{locale === 'zh-CN' ? '编辑模型组' : 'Edit group'}</button>
                <button className="h-12 rounded-2xl bg-[var(--danger)] text-sm font-medium text-white" type="button" onClick={() => setDeleteTarget(detailTarget)}>{locale === 'zh-CN' ? '删除模型组' : 'Delete group'}</button>
              </div>
            </div>
          </AppDialogContent>
        ) : null}
      </Dialog.Root>

      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent className="max-w-6xl" title={editingId ? (locale === 'zh-CN' ? '编辑模型组' : 'Edit group') : (locale === 'zh-CN' ? '新建模型组' : 'Create group')}>
          <form className="flex h-full min-h-0 flex-col overflow-hidden" onSubmit={submit}>
            <div className="hide-scrollbar min-h-0 flex-1 space-y-5 overflow-y-auto pr-1" style={{ maxHeight: 'calc(88vh - 210px)' }}>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <label className="grid gap-2">
                <span className="text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '协议' : 'Protocol'}</span>
                <select className={inputClassName()} value={form.protocol} onChange={(e) => changeProtocol(e.target.value as ProtocolKind)}>
                  {protocolOptions(locale).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '模型组名称' : 'Group name'}</span>
                <input className={inputClassName()} placeholder={locale === 'zh-CN' ? '例如 claude-sonnet-4-6' : 'For example claude-sonnet-4-6'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '匹配正则' : 'Match regex'}</span>
                <input className={inputClassName()} placeholder={locale === 'zh-CN' ? '留空则按模型组名称匹配' : 'Optional, otherwise match by group name'} value={form.match_regex} onChange={(e) => setForm({ ...form, match_regex: e.target.value })} />
              </label>
              </div>

              <div className="grid min-h-0 gap-4 overflow-hidden lg:grid-cols-[1.05fr_0.95fr]">
              <section className={panelClassName('flex min-h-0 flex-col overflow-hidden')}>
                <div className="grid gap-3 border-b border-[var(--line)] px-4 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                  <div className="flex min-w-0 items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel-soft)] px-3">
                    <Search size={14} className="text-[var(--muted)]" />
                    <input className="h-9 min-w-0 flex-1 bg-transparent text-[13px] outline-none" value={candidateSearch} onChange={(e) => setCandidateSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索模型' : 'Search models'} />
                  </div>
                  <div className="flex items-center justify-end gap-2">
                    <button type="button" className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-1.5 text-[12px] text-[var(--text)] disabled:opacity-50" onClick={addMatchedItems} disabled={!matchedCandidates.length}>
                      <Sparkles size={13} />
                      {locale === 'zh-CN' ? `批量加入 ${matchedCandidates.length}` : `Add matched ${matchedCandidates.length}`}
                    </button>
                    <button type="button" className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-1.5 text-[12px] text-[var(--text)] disabled:opacity-50" onClick={() => void refetchCandidates()} disabled={isFetchingCandidates}>
                      <RefreshCcw size={13} />
                      {locale === 'zh-CN' ? '刷新列表' : 'Refresh'}
                    </button>
                  </div>
                </div>

                <div className="hide-scrollbar min-h-0 flex-1 overflow-y-auto px-3 pb-3">
                  <div className="space-y-2">
                    {groupedCandidates.map((channel) => {
                      const currentChannel = channelMap.get(channel.channel_id)
                      const isOpen = expandedChannels.includes(channel.channel_id)
                      const endpoint = channelEndpoint(currentChannel)
                      return (
                        <div key={channel.channel_id} className="overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--panel-strong)]">
                          <button type="button" className="flex w-full items-center gap-3 px-3 py-3 text-left transition hover:bg-[var(--panel-soft)]" onClick={() => toggleChannel(channel.channel_id)}>
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-[13px] font-medium text-[var(--text)]">{channel.channel_name}</div>
                              <div className="mt-1 truncate text-[11px] text-[var(--muted)]">{endpoint}</div>
                            </div>
                            <span className="rounded-full bg-[var(--panel-soft)] px-2 py-0.5 text-[11px] text-[var(--muted)]">{channel.credentials.reduce((total, credential) => total + credential.items.length, 0)}</span>
                            <ChevronDown size={15} className={cn('text-[var(--muted)] transition-transform', isOpen && 'rotate-180')} />
                          </button>
                          {isOpen ? (
                            <div className="space-y-1.5 border-t border-[var(--line)] px-3 py-3">
                              {channel.credentials.map((credential) => (
                                <div key={`${channel.channel_id}-${credential.credential_id}`} className="space-y-1.5 rounded-xl bg-[var(--panel-soft)] p-2.5">
                                  <div className="px-1 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--muted)]">{credential.credential_name || (locale === 'zh-CN' ? '未命名 Key' : 'Unnamed key')}</div>
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
                    {!groupedCandidates.length ? <p className="px-1 py-6 text-center text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '暂无可选模型' : 'No candidates found'}</p> : null}
                  </div>
                </div>
              </section>

              <section className={panelClassName('flex min-h-0 flex-col overflow-hidden')}>
                <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-3">
                  <div className="text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '已选模型' : 'Selected models'}</div>
                  <div className="flex items-center gap-2">
                    <button type="button" className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-2.5 py-1 text-xs text-[var(--muted)]" onClick={() => setAllMembersEnabled(true)}>{locale === 'zh-CN' ? '全开' : 'Enable all'}</button>
                    <button type="button" className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-2.5 py-1 text-xs text-[var(--muted)]" onClick={() => setAllMembersEnabled(false)}>{locale === 'zh-CN' ? '全关' : 'Disable all'}</button>
                    <button type="button" className={cn('rounded-xl border px-2.5 py-1 text-xs', showEnabledOnly ? 'border-[var(--accent)] bg-[var(--panel-soft)] text-[var(--accent)]' : 'border-[var(--line)] bg-[var(--panel)] text-[var(--muted)]')} onClick={() => setShowEnabledOnly((current) => !current)}>{locale === 'zh-CN' ? '仅看启用' : 'Enabled only'}</button>
                    <span className="rounded-full bg-[var(--panel-soft)] px-2.5 py-1 text-xs text-[var(--muted)]">{visibleSelectedItems.length}/{form.items.length}</span>
                  </div>
                </div>
                <div className="hide-scrollbar min-h-0 flex-1 overflow-y-auto p-3">
                  <div className="space-y-1.5">
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
                    )}) : <p className="px-1 py-6 text-center text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '当前筛选下没有成员' : 'No members under current filter'}</p>}
                  </div>
                </div>
              </section>
            </div>
            </div>

            <div className="mt-4 shrink-0 border-t border-[var(--line)] bg-[var(--panel-strong)] pt-4">
              {error ? <p className="mb-3 text-sm text-[var(--danger)]">{error}</p> : null}
              <div className="flex justify-end gap-3">
              <button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white" type="submit">{editingId ? (locale === 'zh-CN' ? '保存模型组' : 'Save group') : (locale === 'zh-CN' ? '创建模型组' : 'Create group')}</button>
              </div>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除模型组' : 'Delete group'} description={locale === 'zh-CN' ? '删除后，该模型组名称将不再参与路由匹配。' : 'This group will no longer participate in routing.'}>
          <div className="grid gap-5 overflow-y-auto pr-1">
            <div className="rounded-2xl bg-[var(--panel)] p-4"><strong>{deleteTarget?.name}</strong></div>
            <div className="flex justify-end gap-3">
              <button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDeleteTarget(null)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-xl bg-[var(--danger)] px-4 py-2.5 text-sm font-medium text-white" type="button" onClick={() => deleteTarget && void remove(deleteTarget)} disabled={busyId === deleteTarget?.id}>{busyId === deleteTarget?.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '确认删除' : 'Delete')}</button>
            </div>
          </div>
        </AppDialogContent>
      </Dialog.Root>
    </section>
  )
}

