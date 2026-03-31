"use client"

import { FormEvent, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquare, Pencil, Plus, Search, SlidersHorizontal, Trash2 } from 'lucide-react'
import { ApiError, Provider, ProtocolKind, ProviderPayload, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { SegmentedControl } from '@/components/ui/segmented-control'

type FormState = {
  name: string
  protocol: ProtocolKind
  base_url: string
  api_key: string
  model_name: string
  status: 'enabled' | 'disabled'
  weight: number
  priority: number
  model_patterns: string
}

type ViewMode = 'cards' | 'list'

const emptyForm: FormState = {
  name: '',
  protocol: 'openai_chat',
  base_url: '',
  api_key: '',
  model_name: '',
  status: 'enabled',
  weight: 1,
  priority: 100,
  model_patterns: ''
}

const protocolOptions: Array<{ value: ProtocolKind; label: string }> = [
  { value: 'openai_chat', label: 'OpenAI Chat' },
  { value: 'openai_responses', label: 'OpenAI Responses' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' }
]

function toForm(item: Provider): FormState {
  return { ...item, model_name: item.model_name ?? '', model_patterns: item.model_patterns.join('\n') }
}

function toPayload(form: FormState): ProviderPayload {
  return {
    name: form.name.trim(),
    protocol: form.protocol,
    base_url: form.base_url.trim(),
    api_key: form.api_key.trim(),
    model_name: form.model_name.trim() || null,
    status: form.status,
    weight: Number(form.weight),
    priority: Number(form.priority),
    headers: {},
    model_patterns: form.model_patterns.split('\n').map((item) => item.trim()).filter(Boolean)
  }
}

function maskKey(value: string) {
  return value.length > 10 ? value.slice(0, 6) + '...' + value.slice(-4) : value || 'n/a'
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-2">
      <span className="text-sm text-[var(--muted)]">{label}</span>
      {children}
    </label>
  )
}

function inputClassName() {
  return 'h-10 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

export function ChannelsScreen() {
  const queryClient = useQueryClient()
  const { locale, t } = useI18n()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Provider | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('cards')
  const [search, setSearch] = useState('')
  const { data, isLoading } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })

  const visibleData = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) {
      return data ?? []
    }
    return (data ?? []).filter((item) => {
      const models = item.model_patterns.join(' ').toLowerCase()
      return item.name.toLowerCase().includes(keyword) || item.base_url.toLowerCase().includes(keyword) || models.includes(keyword)
    })
  }, [data, search])

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['providers'] })
  }

  function openCreate() {
    setEditingId(null)
    setForm(emptyForm)
    setError('')
    setDialogOpen(true)
  }

  function openEdit(item: Provider) {
    setEditingId(item.id)
    setForm(toForm(item))
    setError('')
    setDialogOpen(true)
  }

  async function saveProvider(payload: FormState, providerId: string | null) {
    await apiRequest<Provider>(providerId ? '/providers/' + providerId : '/providers', {
      method: providerId ? 'PUT' : 'POST',
      body: JSON.stringify(toPayload(payload))
    })
    await refresh()
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      await saveProvider(form, editingId)
      setDialogOpen(false)
      setEditingId(null)
      setForm(emptyForm)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存渠道失败' : 'Failed to save channel'))
    }
  }

  async function toggleStatus(item: Provider) {
    setBusyId(item.id)
    setError('')
    try {
      await saveProvider({
        ...toForm(item),
        status: item.status === 'enabled' ? 'disabled' : 'enabled'
      }, item.id)
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
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除渠道失败' : 'Failed to delete channel'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2 text-[var(--muted)]">
        <div className="hidden h-9 items-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 md:flex">
          <Search size={15} />
          <input className="ml-2 w-40 bg-transparent text-sm outline-none" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索渠道' : 'Search'} />
        </div>
        <SegmentedControl value={viewMode} onValueChange={setViewMode} options={[{ value: 'cards', label: locale === 'zh-CN' ? '卡片' : 'Cards' }, { value: 'list', label: locale === 'zh-CN' ? '列表' : 'List' }]} />
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={() => void refresh()} title={t.refresh}>
          <SlidersHorizontal size={16} />
        </button>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={openCreate} title={locale === 'zh-CN' ? '新增渠道' : 'New channel'}>
          <Plus size={16} />
        </button>
      </div>

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载渠道...' : 'Loading channels...'}</p> : null}

      {viewMode === 'cards' ? (
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {visibleData.map((item) => (
            <article key={item.id} className="flex flex-col gap-4 rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)]">
              <header className="relative flex items-center justify-between gap-2">
                <strong className="min-w-0 truncate text-[17px] font-semibold text-[var(--text)]">{item.name}</strong>
                <button
                  type="button"
                  onClick={() => void toggleStatus(item)}
                  disabled={busyId === item.id}
                  className={item.status === 'enabled'
                    ? 'relative h-6 w-11 rounded-full bg-[var(--accent)] transition-colors disabled:opacity-60'
                    : 'relative h-6 w-11 rounded-full bg-[var(--line-strong)] transition-colors disabled:opacity-60'}
                >
                  <span className={item.status === 'enabled'
                    ? 'absolute right-1 top-1 h-4 w-4 rounded-full bg-white'
                    : 'absolute left-1 top-1 h-4 w-4 rounded-full bg-white'} />
                </button>
              </header>

              <dl className="grid grid-cols-1 gap-3">
                <div className="flex items-center justify-between rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-2.5">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(97,168,102,0.12)] text-[var(--accent)]">
                      <MessageSquare className="h-4 w-4" />
                    </span>
                    <dt className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '优先级' : 'Priority'}</dt>
                  </div>
                  <dd className="text-sm font-semibold text-[var(--text)]">{item.priority}</dd>
                </div>

                <div className="flex items-center justify-between rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-2.5">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(97,168,102,0.12)] text-[var(--accent)]">$</span>
                    <dt className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '权重' : 'Weight'}</dt>
                  </div>
                  <dd className="text-sm font-semibold text-[var(--text)]">{item.weight}</dd>
                </div>
              </dl>

              <div className="space-y-2 text-[11px] text-[var(--muted)]">
                <p className="truncate">{protocolOptions.find((option) => option.value === item.protocol)?.label}</p>
                <p className="truncate">{maskKey(item.api_key)} · {item.base_url}</p>
                <p className="line-clamp-2">{(item.model_patterns.length ? item.model_patterns : [item.model_name || (locale === 'zh-CN' ? '未设置模型条件' : 'No selector')]).join(', ')}</p>
              </div>

              <div className="flex items-center justify-end gap-1 text-[var(--muted)]">
                <button className="rounded-lg p-1.5 transition-colors hover:bg-[var(--panel-soft)] hover:text-[var(--text)]" type="button" onClick={() => openEdit(item)} title={locale === 'zh-CN' ? '编辑' : 'Edit'}>
                  <Pencil size={15} />
                </button>
                <button className="rounded-lg p-1.5 transition-colors hover:bg-[rgba(217,111,93,0.10)] hover:text-[var(--danger)]" type="button" onClick={() => setDeleteTarget(item)} title={locale === 'zh-CN' ? '删除' : 'Delete'}>
                  <Trash2 size={15} />
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] shadow-[var(--shadow-sm)]">
          <div className="grid grid-cols-[minmax(0,1.2fr)_0.9fr_1fr_0.8fr_auto] gap-4 border-b border-[var(--line)] px-5 py-3 text-xs font-semibold text-[var(--muted)]">
            <span>{locale === 'zh-CN' ? '渠道' : 'Channel'}</span>
            <span>{locale === 'zh-CN' ? '协议' : 'Protocol'}</span>
            <span>{locale === 'zh-CN' ? '模型规则' : 'Rules'}</span>
            <span>{locale === 'zh-CN' ? '权重 / 优先级' : 'Weight / Priority'}</span>
            <span>{locale === 'zh-CN' ? '操作' : 'Actions'}</span>
          </div>
          <div className="divide-y divide-[var(--line)]">
            {visibleData.map((item) => (
              <div key={item.id} className="grid grid-cols-[minmax(0,1.2fr)_0.9fr_1fr_0.8fr_auto] gap-4 px-5 py-4 text-sm text-[var(--text)]">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <strong className="truncate">{item.name}</strong>
                    <span className={item.status === 'enabled' ? 'rounded-lg bg-[rgba(31,157,104,0.12)] px-2 py-1 text-[11px] text-[var(--success)]' : 'rounded-lg bg-[rgba(192,58,76,0.12)] px-2 py-1 text-[11px] text-[var(--danger)]'}>{item.status === 'enabled' ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}</span>
                  </div>
                  <p className="mt-2 truncate text-[var(--muted)]">{item.base_url}</p>
                </div>
                <span>{protocolOptions.find((option) => option.value === item.protocol)?.label}</span>
                <span className="truncate text-[var(--muted)]">{(item.model_patterns.length ? item.model_patterns : [item.model_name || 'n/a']).join(', ')}</span>
                <span className="text-[var(--muted)]">{item.weight} / {item.priority}</span>
                <div className="flex items-center gap-1 justify-end text-[var(--muted)]">
                  <button className="rounded-lg p-1.5 transition-colors hover:bg-[var(--panel)] hover:text-[var(--text)]" type="button" onClick={() => void toggleStatus(item)} disabled={busyId === item.id}>
                    <SlidersHorizontal size={15} />
                  </button>
                  <button className="rounded-lg p-1.5 transition-colors hover:bg-[var(--panel)] hover:text-[var(--text)]" type="button" onClick={() => openEdit(item)}>
                    <Pencil size={15} />
                  </button>
                  <button className="rounded-lg p-1.5 transition-colors hover:bg-[rgba(217,111,93,0.10)] hover:text-[var(--danger)]" type="button" onClick={() => setDeleteTarget(item)}>
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent
          title={editingId ? (locale === 'zh-CN' ? '编辑渠道' : 'Edit channel') : (locale === 'zh-CN' ? '新建渠道' : 'Create channel')}
          description={locale === 'zh-CN' ? '录入上游地址、协议、模型规则与调度参数。' : 'Configure endpoint, protocol, model rules, and scheduling weights.'}
        >
          <form className="grid gap-4" onSubmit={submit}>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label={locale === 'zh-CN' ? '渠道名称' : 'Channel name'}>
                <input className={inputClassName()} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="FoxCode" />
              </Field>
              <Field label={locale === 'zh-CN' ? '协议类型' : 'Protocol'}>
                <select className={inputClassName()} value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as ProtocolKind })}>
                  {protocolOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Base URL">
              <input className={inputClassName()} value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.openai.com/v1" />
            </Field>
            <Field label="API Key">
              <input className={inputClassName()} value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="sk-..." />
            </Field>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label={locale === 'zh-CN' ? '状态' : 'Status'}>
                <select className={inputClassName()} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as 'enabled' | 'disabled' })}>
                  <option value="enabled">{locale === 'zh-CN' ? '启用' : 'Enabled'}</option>
                  <option value="disabled">{locale === 'zh-CN' ? '停用' : 'Disabled'}</option>
                </select>
              </Field>
              <Field label={locale === 'zh-CN' ? '模型覆写' : 'Model override'}>
                <input className={inputClassName()} value={form.model_name} onChange={(e) => setForm({ ...form, model_name: e.target.value })} placeholder={locale === 'zh-CN' ? '可选' : 'Optional'} />
              </Field>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label={locale === 'zh-CN' ? '权重' : 'Weight'}>
                <input className={inputClassName()} type="number" min={1} value={form.weight} onChange={(e) => setForm({ ...form, weight: Number(e.target.value) || 1 })} />
              </Field>
              <Field label={locale === 'zh-CN' ? '优先级' : 'Priority'}>
                <input className={inputClassName()} type="number" min={1} value={form.priority} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) || 1 })} />
              </Field>
            </div>
            <Field label={locale === 'zh-CN' ? '模型正则' : 'Model regex patterns'}>
              <textarea className={inputClassName() + ' min-h-28 py-3'} value={form.model_patterns} onChange={(e) => setForm({ ...form, model_patterns: e.target.value })} placeholder={locale === 'zh-CN' ? '每行一个正则，例如 ^claude-opus-4-6$' : 'One regex per line'} />
            </Field>
            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-3">
              <button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white" type="submit">{editingId ? (locale === 'zh-CN' ? '保存渠道' : 'Save channel') : (locale === 'zh-CN' ? '创建渠道' : 'Create channel')}</button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent
          className="max-w-lg"
          title={locale === 'zh-CN' ? '确认删除渠道' : 'Delete channel'}
          description={locale === 'zh-CN' ? '删除后该渠道会从路由池中移除，相关模型组需要重新确认。' : 'This removes the channel from routing pools and may affect bound model groups.'}
        >
          <div className="grid gap-5">
            <div className="rounded-2xl bg-[var(--panel)] p-4">
              <strong>{deleteTarget?.name}</strong>
              <p className="mt-2 text-sm text-[var(--muted)]">{deleteTarget?.base_url}</p>
            </div>
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
