"use client"

import { FormEvent, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, LockKeyhole, Pencil, Plus, Search, ShieldCheck, Trash2 } from 'lucide-react'
import { ApiError, GatewayKey, GatewayKeyPayload, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'

type FormState = { name: string; enabled: boolean }

const emptyForm: FormState = { name: 'default-client', enabled: true }

function toForm(item: GatewayKey): FormState {
  return { name: item.name, enabled: item.enabled }
}

function toPayload(form: FormState): GatewayKeyPayload {
  return { name: form.name.trim(), enabled: form.enabled }
}

function maskSecret(secret: string) {
  return secret.length > 18 ? secret.slice(0, 10) + '...' + secret.slice(-6) : secret
}

function inputClassName() {
  return 'w-full rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)] focus:bg-[var(--panel-strong)]'
}

function SectionCard({
  icon: Icon,
  title,
  description,
  children,
  className = ''
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  description?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={'mb-4 break-inside-avoid rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)] ' + className}>
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[rgba(97,168,102,0.14)] text-[var(--accent)]">
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-[var(--text)]">{title}</h3>
          {description ? <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{description}</p> : null}
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  )
}

export function KeysScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<GatewayKey | null>(null)
  const [search, setSearch] = useState('')
  const { data, isLoading } = useQuery({ queryKey: ['gateway-keys'], queryFn: () => apiRequest<GatewayKey[]>('/gateway-keys') })

  const visibleData = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) {
      return data ?? []
    }
    return (data ?? []).filter((item) => item.name.toLowerCase().includes(keyword) || item.secret.toLowerCase().includes(keyword))
  }, [data, search])

  const enabledCount = useMemo(() => (data ?? []).filter((item) => item.enabled).length, [data])
  const disabledCount = (data?.length ?? 0) - enabledCount

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['gateway-keys'] })
  }

  function openCreate() {
    setEditingId(null)
    setForm(emptyForm)
    setError('')
    setDialogOpen(true)
  }

  function openEdit(item: GatewayKey) {
    setEditingId(item.id)
    setForm(toForm(item))
    setError('')
    setDialogOpen(true)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      await apiRequest<GatewayKey>(editingId ? '/gateway-keys/' + editingId : '/gateway-keys', {
        method: editingId ? 'PUT' : 'POST',
        body: JSON.stringify(toPayload(form))
      })
      setDialogOpen(false)
      setEditingId(null)
      setForm(emptyForm)
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存网关密钥失败' : 'Failed to save key'))
    }
  }

  async function remove(item: GatewayKey) {
    setBusyId(item.id)
    setError('')
    try {
      await apiRequest<void>('/gateway-keys/' + item.id, { method: 'DELETE' })
      setDeleteTarget(null)
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除网关密钥失败' : 'Failed to delete key'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-end gap-2 text-[var(--muted)]">
          <div className="hidden items-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 py-2 md:flex">
            <Search size={16} />
            <input className="ml-2 w-40 bg-transparent text-sm outline-none" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索密钥' : 'Search'} />
          </div>
          <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)]" type="button" onClick={() => void refresh()} title={locale === 'zh-CN' ? '刷新' : 'Refresh'}>
            <ShieldCheck size={16} />
          </button>
          <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent)] text-white" type="button" onClick={openCreate} title={locale === 'zh-CN' ? '新增密钥' : 'New key'}>
            <Plus size={16} />
          </button>
      </div>

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载网关密钥...' : 'Loading keys...'}</p> : null}

      <div className="columns-1 gap-4 pb-2 md:columns-2">
        <SectionCard
          icon={KeyRound}
          title={locale === 'zh-CN' ? '凭证概览' : 'Credential overview'}
          description={locale === 'zh-CN' ? '当前所有网关访问密钥的统计。' : 'A summary of all current gateway access keys.'}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{locale === 'zh-CN' ? '密钥总数' : 'Total keys'}</p>
              <strong className="mt-3 block text-[28px] text-[var(--text)]">{data?.length ?? 0}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{locale === 'zh-CN' ? '启用密钥' : 'Enabled'}</p>
              <strong className="mt-3 block text-[28px] text-[var(--text)]">{enabledCount}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{locale === 'zh-CN' ? '停用密钥' : 'Disabled'}</p>
              <strong className="mt-3 block text-[28px] text-[var(--text)]">{disabledCount}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{locale === 'zh-CN' ? '当前视图' : 'Current view'}</p>
              <strong className="mt-3 block text-[18px] text-[var(--text)]">{locale === 'zh-CN' ? '设置分块' : 'Settings blocks'}</strong>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          icon={LockKeyhole}
          title={locale === 'zh-CN' ? '访问策略' : 'Access policy'}
          description={locale === 'zh-CN' ? '密钥删除后客户端会立即失去访问权限，停用则可临时冻结访问。' : 'Deleting a key revokes client access immediately, while disabling it temporarily freezes access.'}
        >
          <div className="space-y-3 text-sm leading-6 text-[var(--muted)]">
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              {locale === 'zh-CN'
                ? '1. 每个密钥会生成独立的 `secret`，用于客户端调用网关时的鉴权。'
                : '1. Each key gets its own `secret`, which is used for client authentication when calling the gateway.'}
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              {locale === 'zh-CN'
                ? '2. 建议按客户端或业务系统拆分密钥，方便追踪、停用和轮换。'
                : '2. Split keys by client or business system so they are easier to trace, disable, and rotate.'}
            </div>
          </div>
        </SectionCard>
      </div>

      <section className="rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '密钥列表' : 'Key list'}</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {locale === 'zh-CN'
                ? '采用与设置页一致的分块卡片布局，便于快速查看与编辑。'
                : 'Uses the same block layout as the settings page for quick review and editing.'}
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
          {visibleData.map((item) => (
            <article key={item.id} className="rounded-[26px] border border-[var(--line)] bg-[var(--panel)] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <strong className="truncate text-[17px] text-[var(--text)]">{item.name}</strong>
                    <span className={item.enabled ? 'rounded-xl bg-[rgba(31,157,104,0.12)] px-2.5 py-1 text-[11px] text-[var(--success)]' : 'rounded-xl bg-[rgba(217,111,93,0.12)] px-2.5 py-1 text-[11px] text-[var(--danger)]'}>
                      {item.enabled ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}
                    </span>
                  </div>
                  <p className="mt-3 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">secret</p>
                  <p className="mt-2 font-mono text-sm break-all text-[var(--text)]">{maskSecret(item.secret)}</p>
                </div>
                <div className="flex items-center gap-2 text-[var(--muted)]">
                  <button type="button" onClick={() => openEdit(item)} className="transition hover:text-[var(--text)]" title={locale === 'zh-CN' ? '编辑密钥' : 'Edit key'}>
                    <Pencil size={16} />
                  </button>
                  <button type="button" onClick={() => setDeleteTarget(item)} className="transition hover:text-[var(--danger)]" title={locale === 'zh-CN' ? '删除密钥' : 'Delete key'}>
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>

        {!isLoading && visibleData.length === 0 ? (
          <div className="mt-5 rounded-3xl border border-dashed border-[var(--line)] bg-[var(--panel)] px-5 py-10 text-center text-sm text-[var(--muted)]">
            {locale === 'zh-CN' ? '当前没有符合条件的密钥。' : 'No matching keys found.'}
          </div>
        ) : null}
      </section>

      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent title={editingId ? (locale === 'zh-CN' ? '编辑密钥' : 'Edit key') : (locale === 'zh-CN' ? '新建密钥' : 'Create key')} description={locale === 'zh-CN' ? '创建或更新下游访问凭证。' : 'Create or update a downstream access credential.'}>
          <form className="grid gap-4" onSubmit={submit}>
            <input className={inputClassName()} placeholder={locale === 'zh-CN' ? '密钥名称' : 'Key name'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <label className="flex items-center gap-3 rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm text-[var(--text)]">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              {locale === 'zh-CN' ? '启用该密钥' : 'Enable this key'}
            </label>
            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-3">
              <button className="rounded-full border border-[var(--line)] bg-[var(--panel-strong)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-full bg-[var(--accent)] px-5 py-2.5 text-sm font-medium text-white" type="submit">{editingId ? (locale === 'zh-CN' ? '保存密钥' : 'Save key') : (locale === 'zh-CN' ? '创建密钥' : 'Create key')}</button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除密钥' : 'Delete key'} description={locale === 'zh-CN' ? '删除后，使用该密钥的客户端将无法继续调用网关。' : 'Clients using this key will lose gateway access.'}>
          <div className="grid gap-5">
            <div className="rounded-[22px] bg-[var(--panel)] p-4">
              <strong className="text-[var(--text)]">{deleteTarget?.name}</strong>
              <p className="mt-2 font-mono text-sm text-[var(--muted)]">{deleteTarget?.secret}</p>
            </div>
            <div className="flex justify-end gap-3">
              <button className="rounded-full border border-[var(--line)] bg-[var(--panel-strong)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDeleteTarget(null)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-full bg-[var(--danger)] px-5 py-2.5 text-sm font-medium text-white" type="button" onClick={() => deleteTarget && void remove(deleteTarget)} disabled={busyId === deleteTarget?.id}>{busyId === deleteTarget?.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '确认删除' : 'Delete')}</button>
            </div>
          </div>
        </AppDialogContent>
      </Dialog.Root>
    </section>
  )
}
