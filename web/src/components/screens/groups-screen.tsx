"use client"

import { FormEvent, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Boxes, GitBranch, Plus, Route, Trash2 } from 'lucide-react'
import { ApiError, ModelGroup, ModelGroupPayload, ProtocolKind, Provider, RoutingStrategy, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { MetricCard } from '@/components/ui/metric-card'
import { PageHeader } from '@/components/ui/page-header'
import { SegmentedControl } from '@/components/ui/segmented-control'

type FormState = {
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  provider_ids: string[]
  enabled: boolean
}

type ViewMode = 'cards' | 'list'

const emptyForm: FormState = { name: '', protocol: 'openai_chat', strategy: 'round_robin', provider_ids: [], enabled: true }

function toForm(item: ModelGroup): FormState {
  return { ...item }
}

function toPayload(form: FormState): ModelGroupPayload {
  return { ...form, name: form.name.trim() }
}

function inputClassName() {
  return 'rounded-[22px] border border-[var(--line-strong)] bg-white/88 px-4 py-3 text-[var(--text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] outline-none transition focus:border-[var(--accent)] focus:bg-white'
}

export function GroupsScreen() {
  const queryClient = useQueryClient()
  const { locale, t } = useI18n()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ModelGroup | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('cards')
  const { data: groups, isLoading } = useQuery({ queryKey: ['groups'], queryFn: () => apiRequest<ModelGroup[]>('/model-groups') })
  const { data: providers } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })

  const matchedProviders = useMemo(() => (providers ?? []).filter((item) => item.protocol === form.protocol), [providers, form.protocol])
  const enabledCount = useMemo(() => (groups ?? []).filter((item) => item.enabled).length, [groups])
  const protocolCount = useMemo(() => new Set((groups ?? []).map((item) => item.protocol)).size, [groups])

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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      await apiRequest<ModelGroup>(editingId ? '/model-groups/' + editingId : '/model-groups', {
        method: editingId ? 'PUT' : 'POST',
        body: JSON.stringify(toPayload(form))
      })
      setDialogOpen(false)
      setEditingId(null)
      setForm(emptyForm)
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存模型组失败' : 'Failed to save group'))
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
      provider_ids: current.provider_ids.includes(id) ? current.provider_ids.filter((item) => item !== id) : [...current.provider_ids, id]
    }))
  }

  return (
    <section className="grid gap-6">
      <PageHeader
        eyebrow={locale === 'zh-CN' ? '模型组' : 'Model groups'}
        title={locale === 'zh-CN' ? '将外部模型名映射到可轮询的渠道集合' : 'Map external model names to routable channel pools'}
        description={locale === 'zh-CN' ? '模型组优先级高于渠道正则，适合做同名模型聚合、权重调度和故障切换。' : 'Groups take precedence over provider regex rules and are ideal for pooled routing.'}
        actions={
          <>
            <SegmentedControl value={viewMode} onValueChange={setViewMode} options={[{ value: 'cards', label: locale === 'zh-CN' ? '卡片' : 'Cards' }, { value: 'list', label: locale === 'zh-CN' ? '列表' : 'List' }]} />
            <button className="rounded-full border border-white/80 bg-white px-4 py-2.5 text-sm font-medium text-[var(--text)] shadow-[0_16px_30px_rgba(24,46,79,0.08)]" type="button" onClick={() => void refresh()}>{t.refresh}</button>
            <button className="inline-flex items-center gap-2 rounded-full bg-[linear-gradient(135deg,#2f6fed,#5a8fff)] px-4 py-2.5 text-sm font-medium text-white shadow-[0_18px_36px_rgba(47,111,237,0.28)]" type="button" onClick={openCreate}><Plus size={16} />{locale === 'zh-CN' ? '新增模型组' : 'New group'}</button>
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Boxes} label={locale === 'zh-CN' ? '模型组总数' : 'Groups'} value={groups?.length ?? 0} tone="accent" />
        <MetricCard icon={GitBranch} label={locale === 'zh-CN' ? '启用模型组' : 'Enabled'} value={enabledCount} />
        <MetricCard icon={Route} label={locale === 'zh-CN' ? '协议种类' : 'Protocols'} value={protocolCount} />
        <MetricCard icon={Boxes} label={locale === 'zh-CN' ? '已绑定渠道' : 'Bound providers'} value={(groups ?? []).reduce((count, item) => count + item.provider_ids.length, 0)} />
      </div>

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载模型组...' : 'Loading groups...'}</p> : null}

      {viewMode === 'cards' ? (
        <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
          {groups?.map((item) => (
            <article key={item.id} className="rounded-[30px] border border-white/70 bg-[rgba(255,255,255,0.78)] p-5 shadow-[0_18px_44px_rgba(24,46,79,0.08)] backdrop-blur-[18px]">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="text-lg tracking-[-0.02em]">{item.name}</strong>
                    <span className={item.enabled ? 'rounded-full bg-[rgba(31,157,104,0.12)] px-3 py-1 text-xs text-[var(--success)]' : 'rounded-full bg-[rgba(192,58,76,0.12)] px-3 py-1 text-xs text-[var(--danger)]'}>{item.enabled ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}</span>
                  </div>
                  <p className="mt-3 text-sm text-[var(--muted)]">{item.protocol} · {item.strategy}</p>
                </div>
                <div className="flex gap-2">
                  <button className="rounded-full border border-white/80 bg-white px-3 py-2 text-sm shadow-[0_10px_24px_rgba(24,46,79,0.08)]" type="button" onClick={() => openEdit(item)}>{locale === 'zh-CN' ? '编辑' : 'Edit'}</button>
                  <button className="rounded-full border border-[rgba(192,58,76,0.18)] bg-[rgba(192,58,76,0.08)] p-2 text-[var(--danger)]" type="button" onClick={() => setDeleteTarget(item)}><Trash2 size={16} /></button>
                </div>
              </div>
              <div className="mt-4 rounded-[24px] border border-white/70 bg-[rgba(247,249,253,0.84)] p-4">
                <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '渠道链路' : 'Provider chain'}</p>
                <p className="mt-2 text-sm leading-7 text-[var(--text)]">{item.provider_ids.join(' → ') || (locale === 'zh-CN' ? '未绑定渠道' : 'No providers')}</p>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-[30px] border border-white/70 bg-[rgba(255,255,255,0.74)] shadow-[0_18px_44px_rgba(24,46,79,0.08)] backdrop-blur-[20px]">
          <div className="grid grid-cols-[minmax(0,1.2fr)_0.8fr_0.8fr_1fr_auto] gap-4 border-b border-white/70 px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">
            <span>{locale === 'zh-CN' ? '模型组' : 'Group'}</span>
            <span>{locale === 'zh-CN' ? '协议' : 'Protocol'}</span>
            <span>{locale === 'zh-CN' ? '策略' : 'Strategy'}</span>
            <span>{locale === 'zh-CN' ? '渠道数' : 'Providers'}</span>
            <span>{locale === 'zh-CN' ? '操作' : 'Actions'}</span>
          </div>
          <div className="divide-y divide-white/60">
            {groups?.map((item) => (
              <div key={item.id} className="grid grid-cols-[minmax(0,1.2fr)_0.8fr_0.8fr_1fr_auto] gap-4 px-5 py-4 text-sm text-[var(--text)]">
                <div>
                  <div className="flex items-center gap-2">
                    <strong>{item.name}</strong>
                    <span className={item.enabled ? 'rounded-full bg-[rgba(31,157,104,0.12)] px-2.5 py-1 text-[11px] text-[var(--success)]' : 'rounded-full bg-[rgba(192,58,76,0.12)] px-2.5 py-1 text-[11px] text-[var(--danger)]'}>{item.enabled ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}</span>
                  </div>
                  <p className="mt-2 text-[var(--muted)]">{item.provider_ids.join(' → ') || 'n/a'}</p>
                </div>
                <span>{item.protocol}</span>
                <span>{item.strategy}</span>
                <span>{item.provider_ids.length}</span>
                <div className="flex gap-2">
                  <button className="rounded-full border border-white/80 bg-white px-3 py-2 text-sm shadow-[0_10px_24px_rgba(24,46,79,0.08)]" type="button" onClick={() => openEdit(item)}>{locale === 'zh-CN' ? '编辑' : 'Edit'}</button>
                  <button className="rounded-full border border-[rgba(192,58,76,0.18)] bg-[rgba(192,58,76,0.08)] p-2 text-[var(--danger)]" type="button" onClick={() => setDeleteTarget(item)}><Trash2 size={16} /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent title={editingId ? (locale === 'zh-CN' ? '编辑模型组' : 'Edit group') : (locale === 'zh-CN' ? '新建模型组' : 'Create group')} description={locale === 'zh-CN' ? '选择协议、路由策略以及参与轮询的渠道。' : 'Pick the protocol, routing strategy, and providers in the pool.'}>
          <form className="grid gap-4" onSubmit={submit}>
            <div className="grid gap-4 md:grid-cols-2">
              <input className={inputClassName()} placeholder={locale === 'zh-CN' ? '外部模型名' : 'External model name'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <select className={inputClassName()} value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as ProtocolKind, provider_ids: [] })}>
                <option value="openai_chat">OpenAI Chat</option>
                <option value="openai_responses">OpenAI Responses</option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Gemini</option>
              </select>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <select className={inputClassName()} value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value as RoutingStrategy })}>
                <option value="round_robin">Round Robin</option>
                <option value="weighted">Weighted</option>
                <option value="failover">Failover</option>
              </select>
              <label className="flex items-center gap-3 rounded-[22px] border border-[var(--line-strong)] bg-white/88 px-4 py-3 text-sm text-[var(--muted)]">
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
                {locale === 'zh-CN' ? '启用模型组' : 'Enable group'}
              </label>
            </div>
            <div className="grid gap-2 rounded-[24px] border border-white/70 bg-[rgba(247,249,253,0.84)] p-3">
              {matchedProviders.map((item) => (
                <label key={item.id} className="flex cursor-pointer items-center gap-3 rounded-[20px] border border-white/80 bg-white px-4 py-3 text-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
                  <input type="checkbox" checked={form.provider_ids.includes(item.id)} onChange={() => toggleProvider(item.id)} />
                  <span>{item.id} · {item.name}</span>
                </label>
              ))}
            </div>
            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-3">
              <button className="rounded-full border border-white/80 bg-white px-4 py-2.5 text-sm font-medium text-[var(--text)] shadow-[0_10px_24px_rgba(24,46,79,0.08)]" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-full bg-[linear-gradient(135deg,#2f6fed,#5a8fff)] px-5 py-2.5 text-sm font-medium text-white shadow-[0_18px_36px_rgba(47,111,237,0.28)]" type="submit">{editingId ? (locale === 'zh-CN' ? '保存模型组' : 'Save group') : (locale === 'zh-CN' ? '创建模型组' : 'Create group')}</button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除模型组' : 'Delete group'} description={locale === 'zh-CN' ? '删除后该模型名将不再命中这组渠道。' : 'This removes the routing group for the external model name.'}>
          <div className="grid gap-5">
            <div className="rounded-[24px] border border-white/70 bg-[rgba(247,249,253,0.86)] p-4">
              <strong>{deleteTarget?.name}</strong>
              <p className="mt-2 text-sm text-[var(--muted)]">{deleteTarget?.provider_ids.join(' → ')}</p>
            </div>
            <div className="flex justify-end gap-3">
              <button className="rounded-full border border-white/80 bg-white px-4 py-2.5 text-sm font-medium text-[var(--text)] shadow-[0_10px_24px_rgba(24,46,79,0.08)]" type="button" onClick={() => setDeleteTarget(null)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-full bg-[linear-gradient(135deg,#e24f66,#c03a4c)] px-5 py-2.5 text-sm font-medium text-white shadow-[0_18px_36px_rgba(192,58,76,0.24)]" type="button" onClick={() => deleteTarget && void remove(deleteTarget)} disabled={busyId === deleteTarget?.id}>{busyId === deleteTarget?.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '确认删除' : 'Delete')}</button>
            </div>
          </div>
        </AppDialogContent>
      </Dialog.Root>
    </section>
  )
}
