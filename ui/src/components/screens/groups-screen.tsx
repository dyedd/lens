"use client"

import { FormEvent, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Layers3, Pencil, Plus, RefreshCcw, Search, Trash2, X } from 'lucide-react'
import { ApiError, ModelGroup, ModelGroupPayload, ProtocolKind, Provider, RoutePreview, RoutingStrategy, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { cn } from '@/lib/cn'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'

type FormState = {
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  provider_ids: string[]
  enabled: boolean
}

const emptyForm: FormState = {
  name: '',
  protocol: 'openai_chat',
  strategy: 'round_robin',
  provider_ids: [],
  enabled: true,
}

const protocolOptions: Array<{ value: ProtocolKind; label: string }> = [
  { value: 'openai_chat', label: 'OpenAI Chat' },
  { value: 'openai_responses', label: 'OpenAI Responses' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
]

const strategyOptions: Array<{ value: RoutingStrategy; zh: string; en: string }> = [
  { value: 'round_robin', zh: '轮询', en: 'Round Robin' },
  { value: 'weighted', zh: '加权', en: 'Weighted' },
  { value: 'failover', zh: '故障转移', en: 'Failover' },
]

function inputClassName() {
  return 'h-10 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-[13px] text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function panelClassName() {
  return 'rounded-[24px] border border-[var(--line)] bg-[var(--panel)]'
}

function toForm(item: ModelGroup): FormState {
  return {
    name: item.name,
    protocol: item.protocol,
    strategy: item.strategy,
    provider_ids: item.provider_ids,
    enabled: item.enabled,
  }
}

function toPayload(form: FormState): ModelGroupPayload {
  return {
    name: form.name.trim(),
    protocol: form.protocol,
    strategy: form.strategy,
    provider_ids: form.provider_ids,
    enabled: form.enabled,
  }
}

function SwitchButton({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative h-6 w-11 rounded-full transition-colors duration-200',
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

function SwitchIndicator({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'relative h-6 w-11 rounded-full transition-colors duration-200',
        checked ? 'bg-[var(--accent)]' : 'bg-[var(--line-strong)]'
      )}
    >
      <span
        className={cn(
          'absolute top-1 h-4 w-4 rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,0.18)] transition-all duration-200',
          checked ? 'right-1' : 'left-1'
        )}
      />
    </span>
  )
}

export function GroupsScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const [search, setSearch] = useState('')
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null)

  const { data: groups, isLoading } = useQuery({ queryKey: ['groups'], queryFn: () => apiRequest<ModelGroup[]>('/model-groups') })
  const { data: providers } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })
  const { data: previews } = useQuery({
    queryKey: ['group-previews', groups],
    enabled: Boolean(groups?.length),
    queryFn: async () => {
      const items = await Promise.all((groups ?? []).map(async (group) => {
        const preview = await apiRequest<RoutePreview>('/router/preview', {
          method: 'POST',
          body: JSON.stringify({ protocol: group.protocol, model: group.name }),
        })
        return [group.id, preview] as const
      }))
      return new Map(items)
    },
  })

  const providerMap = useMemo(() => {
    const map = new Map<string, Provider>()
    for (const item of providers ?? []) {
      map.set(item.id, item)
    }
    return map
  }, [providers])

  const matchedProviders = useMemo(
    () => (providers ?? []).filter((item) => item.protocol === form.protocol),
    [providers, form.protocol]
  )

  const visibleGroups = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) return groups ?? []
    return (groups ?? []).filter((group) => {
      const providerNames = group.provider_ids.map((id) => providerMap.get(id)?.name ?? id).join(' ').toLowerCase()
      return group.name.toLowerCase().includes(keyword) || providerNames.includes(keyword)
    })
  }, [groups, providerMap, search])

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['groups'] }),
      queryClient.invalidateQueries({ queryKey: ['providers'] }),
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
      body: JSON.stringify(toPayload(payload)),
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
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存模型组失败' : 'Failed to save group'))
    }
  }

  async function toggleEnabled(item: ModelGroup) {
    setBusyId(item.id)
    setError('')
    try {
      await saveGroup({ ...item, enabled: !item.enabled }, item.id)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '更新模型组状态失败' : 'Failed to update group status'))
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
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除模型组失败' : 'Failed to delete group'))
    } finally {
      setBusyId(null)
    }
  }

  function toggleProvider(id: string) {
    setForm((current) => ({
      ...current,
      provider_ids: current.provider_ids.includes(id)
        ? current.provider_ids.filter((item) => item !== id)
        : [...current.provider_ids, id],
    }))
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2 text-[var(--muted)]">
        <div className="hidden h-9 items-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 md:flex">
          <Search size={15} />
          <input className="ml-2 w-40 bg-transparent text-[13px] outline-none" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索模型组' : 'Search groups'} />
        </div>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={() => void refresh()}>
          <RefreshCcw size={15} />
        </button>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={openCreate}>
          <Plus size={15} />
        </button>
      </div>

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载模型组...' : 'Loading groups...'}</p> : null}

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {visibleGroups.map((group) => {
          const selectedProviders = group.provider_ids.map((id) => providerMap.get(id)).filter(Boolean) as Provider[]
          const preview = previews?.get(group.id)
          const previewProviders = (preview?.matched_provider_ids ?? []).map((id) => providerMap.get(id)).filter(Boolean) as Provider[]
          return (
            <article key={group.id} className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[15px] font-semibold text-[var(--text)]">{group.name}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
                    <span>{protocolOptions.find((item) => item.value === group.protocol)?.label ?? group.protocol}</span>
                    <span className="rounded-full bg-[var(--panel-soft)] px-2 py-0.5">{group.enabled ? (locale === 'zh-CN' ? '已启用' : 'Enabled') : (locale === 'zh-CN' ? '已停用' : 'Disabled')}</span>
                    <span className="rounded-full bg-[var(--panel-soft)] px-2 py-0.5">{locale === 'zh-CN' ? `渠道 ${group.provider_ids.length}` : `${group.provider_ids.length} providers`}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <SwitchButton checked={group.enabled} onChange={() => void toggleEnabled(group)} />
                  <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--text)]" onClick={() => openEdit(group)}><Pencil size={15} /></button>
                  <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--text)]" onClick={() => void navigator.clipboard.writeText(group.name)}><Copy size={15} /></button>
                  <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--danger)] transition hover:bg-[rgba(217,111,93,0.08)]" onClick={() => setDeleteTarget(group)}><Trash2 size={15} /></button>
                </div>
              </div>

              <div className="mt-4 grid gap-3">
                <div className={panelClassName() + ' p-3'}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium uppercase tracking-[0.08em] text-[var(--muted)]">{locale === 'zh-CN' ? '策略' : 'Strategy'}</span>
                    <span className="rounded-full bg-[var(--accent-2)] px-2.5 py-1 text-xs text-[var(--accent)]">{strategyOptions.find((item) => item.value === group.strategy)?.[locale === 'zh-CN' ? 'zh' : 'en']}</span>
                  </div>
                </div>

                <div className={panelClassName() + ' p-3'}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium uppercase tracking-[0.08em] text-[var(--muted)]">{locale === 'zh-CN' ? '路由预览' : 'Route preview'}</span>
                    <span className="rounded-full bg-[var(--panel-soft)] px-2.5 py-1 text-xs text-[var(--muted)]">{previewProviders.length}</span>
                  </div>
                  <div className="mt-3 space-y-2">
                    {previewProviders.length ? previewProviders.map((provider) => (
                      <div key={provider.id} className="rounded-2xl bg-[var(--panel-soft)] px-3 py-2.5">
                        <div className="truncate text-[13px] font-medium text-[var(--text)]">{provider.name}</div>
                        <div className="mt-1 truncate text-xs text-[var(--muted)]">{provider.base_url}</div>
                      </div>
                    )) : <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '当前没有命中渠道' : 'No providers matched'}</p>}
                  </div>
                </div>

                <div className={panelClassName() + ' p-3'}>
                  <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.08em] text-[var(--muted)]">
                    <Layers3 size={14} />
                    {locale === 'zh-CN' ? '渠道' : 'Providers'}
                  </div>
                  <div className="mt-3 space-y-2">
                    {selectedProviders.length ? selectedProviders.map((provider) => (
                      <div key={provider.id} className="rounded-2xl bg-[var(--panel-soft)] px-3 py-2.5">
                        <div className="truncate text-[13px] font-medium text-[var(--text)]">{provider.name}</div>
                        <div className="mt-1 truncate text-xs text-[var(--muted)]">{provider.base_url}</div>
                      </div>
                    )) : <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '暂无渠道' : 'No providers'}</p>}
                  </div>
                </div>
              </div>
            </article>
          )
        })}
      </div>

      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent className="max-w-4xl" title={editingId ? (locale === 'zh-CN' ? '编辑模型组' : 'Edit group') : (locale === 'zh-CN' ? '新建模型组' : 'Create group')}>
          <form className="grid gap-5" onSubmit={submit}>
            <div className="grid gap-4 md:grid-cols-2">
              <input className={inputClassName()} placeholder={locale === 'zh-CN' ? '模型组名称' : 'Group name'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <select className={inputClassName()} value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as ProtocolKind, provider_ids: [] })}>
                {protocolOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </div>

            <div className="grid gap-4 md:grid-cols-[1fr_auto]">
              <select className={inputClassName()} value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value as RoutingStrategy })}>
                {strategyOptions.map((item) => <option key={item.value} value={item.value}>{locale === 'zh-CN' ? item.zh : item.en}</option>)}
              </select>
              <div className="flex items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4">
                <span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '启用' : 'Enabled'}</span>
                <SwitchButton checked={form.enabled} onChange={(checked) => setForm({ ...form, enabled: checked })} />
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel)] p-4">
              <div className="text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '选择渠道' : 'Select providers'}</div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {matchedProviders.map((item) => {
                  const checked = form.provider_ids.includes(item.id)
                  return (
                    <button key={item.id} type="button" onClick={() => toggleProvider(item.id)} className={cn('rounded-2xl border px-3 py-3 text-left transition', checked ? 'border-[var(--accent)] bg-[var(--panel-strong)]' : 'border-[var(--line)] bg-transparent hover:border-[var(--line-strong)]')}>
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-[13px] font-medium text-[var(--text)]">{item.name}</div>
                          <div className="mt-1 truncate text-xs text-[var(--muted)]">{item.base_url}</div>
                        </div>
                        <SwitchIndicator checked={checked} />
                      </div>
                    </button>
                  )
                })}
                {matchedProviders.length === 0 ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '当前协议下没有可选渠道' : 'No providers available for this protocol'}</p> : null}
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--line)] bg-[var(--panel)] p-4">
              <div className="text-sm font-medium text-[var(--text)]">{locale === 'zh-CN' ? '已选渠道' : 'Selected providers'}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {form.provider_ids.length ? form.provider_ids.map((providerId) => {
                  const provider = providerMap.get(providerId)
                  return (
                    <span key={providerId} className="inline-flex items-center gap-1 rounded-full bg-[var(--panel-strong)] px-3 py-1.5 text-xs text-[var(--text)]">
                      {provider?.name ?? providerId}
                      <button type="button" className="text-[var(--muted)] transition hover:text-[var(--text)]" onClick={() => toggleProvider(providerId)}>
                        <X size={13} />
                      </button>
                    </span>
                  )
                }) : <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '暂未选择渠道' : 'No providers selected'}</p>}
              </div>
            </div>

            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-3">
              <button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white" type="submit">{editingId ? (locale === 'zh-CN' ? '保存模型组' : 'Save group') : (locale === 'zh-CN' ? '创建模型组' : 'Create group')}</button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除模型组' : 'Delete group'} description={locale === 'zh-CN' ? '删除后，该模型组名称将不再参与路由匹配。' : 'This group will no longer participate in routing.'}>
          <div className="grid gap-5">
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
