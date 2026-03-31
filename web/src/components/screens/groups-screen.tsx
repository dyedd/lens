"use client"

import { FormEvent, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Pencil, Plus, RefreshCcw, Search, Trash2 } from 'lucide-react'
import { ApiError, ModelGroup, ModelGroupPayload, ProtocolKind, Provider, RoutingStrategy, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'

type FormState = {
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  provider_ids: string[]
  enabled: boolean
}

const emptyForm: FormState = { name: '', protocol: 'openai_chat', strategy: 'round_robin', provider_ids: [], enabled: true }

const strategyOptions: Array<{ value: RoutingStrategy; zh: string; en: string }> = [
  { value: 'round_robin', zh: '轮询', en: 'Round Robin' },
  { value: 'weighted', zh: '加权分配', en: 'Weighted' },
  { value: 'failover', zh: '故障转移', en: 'Failover' },
]

function toForm(item: ModelGroup): FormState {
  return { ...item }
}

function toPayload(form: FormState): ModelGroupPayload {
  return { ...form, name: form.name.trim() }
}

function inputClassName() {
  return 'h-10 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

export function GroupsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null)
  const [search, setSearch] = useState('')
  const { data: groups, isLoading } = useQuery({ queryKey: ['groups'], queryFn: () => apiRequest<ModelGroup[]>('/model-groups') })
  const { data: providers } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })

  const matchedProviders = useMemo(() => (providers ?? []).filter((item) => item.protocol === form.protocol), [providers, form.protocol])

  const providerMap = useMemo(() => {
    const map = new Map<string, Provider>()
    for (const item of providers ?? []) {
      map.set(item.id, item)
    }
    return map
  }, [providers])

  const visibleGroups = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) {
      return groups ?? []
    }
    return (groups ?? []).filter((group) => {
      const providerNames = group.provider_ids.map((id) => providerMap.get(id)?.name ?? id).join(' ').toLowerCase()
      return group.name.toLowerCase().includes(keyword) || providerNames.includes(keyword)
    })
  }, [groups, providerMap, search])

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['groups'] }),
      queryClient.invalidateQueries({ queryKey: ['providers'] })
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
    await apiRequest<ModelGroup>(groupId ? '/model-groups/' + groupId : '/model-groups', {
      method: groupId ? 'PUT' : 'POST',
      body: JSON.stringify(toPayload(payload))
    })
    await refresh()
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
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存分组失败' : 'Failed to save group'))
    }
  }

  async function switchStrategy(group: ModelGroup, strategy: RoutingStrategy) {
    if (group.strategy === strategy) {
      return
    }
    setBusyId(group.id)
    setError('')
    try {
      await saveGroup({ ...group, strategy }, group.id)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '更新策略失败' : 'Failed to update strategy'))
    } finally {
      setBusyId(null)
    }
  }

  async function remove(item: ModelGroup) {
    setBusyId(item.id)
    setError('')
    try {
      await apiRequest<void>('/model-groups/' + item.id, { method: 'DELETE' })
      setDeleteTarget(null)
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除分组失败' : 'Failed to delete group'))
    } finally {
      setBusyId(null)
    }
  }

  function toggleProvider(id: string) {
    setForm((current) => ({
      ...current,
      provider_ids: current.provider_ids.includes(id) ? current.provider_ids.filter((item) => item !== id) : [...current.provider_ids, id]
    }))
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2 text-[var(--muted)]">
        <div className="hidden h-9 items-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 md:flex">
          <Search size={15} />
          <input className="ml-2 w-40 bg-transparent text-sm outline-none" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索分组' : 'Search'} />
        </div>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={() => void refresh()} title={locale === 'zh-CN' ? '刷新' : 'Refresh'}>
          <RefreshCcw size={15} />
        </button>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={openCreate} title={locale === 'zh-CN' ? '新增分组' : 'New group'}>
          <Plus size={15} />
        </button>
      </div>

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载分组...' : 'Loading groups...'}</p> : null}

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {visibleGroups.map((group) => (
          <article key={group.id} className="flex flex-col rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
            <header className="relative mb-3 flex items-start justify-between gap-3">
              <strong className="truncate pr-2 text-[16px] font-semibold text-[var(--text)]">{group.name}</strong>
              <div className="flex items-center gap-1 text-[var(--muted)]">
                <button type="button" onClick={() => openEdit(group)} className="rounded-lg p-1.5 transition-colors hover:bg-[var(--panel-soft)] hover:text-[var(--text)]"><Pencil size={15} /></button>
                <button type="button" onClick={() => void navigator.clipboard.writeText(group.name)} className="rounded-lg p-1.5 transition-colors hover:bg-[var(--panel-soft)] hover:text-[var(--text)]"><Copy size={15} /></button>
                <button type="button" onClick={() => setDeleteTarget(group)} className="rounded-lg p-1.5 transition-colors hover:bg-[rgba(217,111,93,0.10)] hover:text-[var(--danger)]"><Trash2 size={15} /></button>
              </div>
            </header>

            <div className="mb-3 flex gap-1">
              {strategyOptions.map((item) => {
                const active = item.value === group.strategy
                return (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => void switchStrategy(group, item.value)}
                    disabled={busyId === group.id}
                    className={active
                      ? 'flex-1 rounded-lg bg-[var(--accent)] py-1 text-center text-xs text-white disabled:opacity-60'
                      : 'flex-1 rounded-lg bg-[var(--panel-soft)] py-1 text-center text-xs text-[var(--text)] disabled:opacity-60'}
                  >
                    {locale === 'zh-CN' ? item.zh : item.en}
                  </button>
                )
              })}
            </div>

            <section className="relative h-[25rem] overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--panel)]">
              <div className="space-y-2 p-3">
                {group.provider_ids.map((providerId, index) => {
                  const provider = providerMap.get(providerId)
                  return (
                    <div key={providerId + index} className="flex items-center gap-3 rounded-2xl bg-[var(--panel-soft)] px-3 py-3">
                      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[rgba(97,168,102,0.16)] text-xs font-semibold text-[var(--accent)]">{index + 1}</span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-[var(--text)]">{provider?.name ?? providerId}</p>
                        <p className="truncate text-xs text-[var(--muted)]">{provider?.base_url ?? providerId}</p>
                      </div>
                    </div>
                  )
                })}
                {group.provider_ids.length === 0 ? <p className="px-2 py-3 text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '暂无渠道' : 'No providers'}</p> : null}
              </div>
            </section>
          </article>
        ))}
      </div>

      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent title={editingId ? (locale === 'zh-CN' ? '编辑分组' : 'Edit group') : (locale === 'zh-CN' ? '新建分组' : 'Create group')} description={locale === 'zh-CN' ? '选择协议、分配策略和参与分组的渠道。' : 'Select protocol, routing strategy, and providers in the group.'}>
          <form className="grid gap-4" onSubmit={submit}>
            <div className="grid gap-4 md:grid-cols-2">
              <input className={inputClassName()} placeholder={locale === 'zh-CN' ? '分组名' : 'Group name'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <select className={inputClassName()} value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as ProtocolKind, provider_ids: [] })}>
                <option value="openai_chat">OpenAI Chat</option>
                <option value="openai_responses">OpenAI Responses</option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Gemini</option>
              </select>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <select className={inputClassName()} value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value as RoutingStrategy })}>
                {strategyOptions.map((item) => <option key={item.value} value={item.value}>{locale === 'zh-CN' ? item.zh : item.en}</option>)}
              </select>
              <label className="flex items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
                {locale === 'zh-CN' ? '启用分组' : 'Enable group'}
              </label>
            </div>

            <div className="grid gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3">
              {matchedProviders.map((item) => (
                <label key={item.id} className="flex cursor-pointer items-center gap-3 rounded-xl bg-[var(--panel-soft)] px-4 py-3 text-sm text-[var(--text)]">
                  <input type="checkbox" checked={form.provider_ids.includes(item.id)} onChange={() => toggleProvider(item.id)} />
                  <span>{item.name}</span>
                </label>
              ))}
            </div>

            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-3">
              <button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm text-white" type="submit">{editingId ? (locale === 'zh-CN' ? '保存分组' : 'Save group') : (locale === 'zh-CN' ? '创建分组' : 'Create group')}</button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除分组' : 'Delete group'} description={locale === 'zh-CN' ? '删除后，该分组名称将不再参与路由匹配。' : 'This group will no longer participate in routing.'}>
          <div className="grid gap-5">
            <div className="rounded-2xl bg-[var(--panel)] p-4">
              <strong>{deleteTarget?.name}</strong>
            </div>
            <div className="flex justify-end gap-3">
              <button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDeleteTarget(null)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-xl bg-[var(--danger)] px-4 py-2.5 text-sm text-white" type="button" onClick={() => deleteTarget && void remove(deleteTarget)} disabled={busyId === deleteTarget?.id}>{busyId === deleteTarget?.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '确认删除' : 'Delete')}</button>
            </div>
          </div>
        </AppDialogContent>
      </Dialog.Root>
    </section>
  )
}
