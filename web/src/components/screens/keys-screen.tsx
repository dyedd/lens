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
  return 'h-10 w-full rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function SectionCard({
  icon: Icon,
  title,
  children,
  className = ''
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={'break-inside-avoid rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)] ' + className}>
      <h2 className="flex items-center gap-2 text-base font-semibold text-[var(--text)]">
        <Icon className="h-4 w-4 text-[var(--muted)]" />
        {title}
      </h2>
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
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2 text-[var(--muted)]">
        <div className="hidden h-9 items-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 md:flex">
          <Search size={15} />
          <input className="ml-2 w-40 bg-transparent text-sm outline-none" value={search} onChange={(e) => setSearch(e.target.value)} placeholder={locale === 'zh-CN' ? '搜索密钥' : 'Search'} />
        </div>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={() => void refresh()} title={locale === 'zh-CN' ? '刷新' : 'Refresh'}>
          <ShieldCheck size={16} />
        </button>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] transition-colors hover:text-[var(--text)]" type="button" onClick={openCreate} title={locale === 'zh-CN' ? '新增密钥' : 'New key'}>
          <Plus size={16} />
        </button>
      </div>

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载网关密钥...' : 'Loading keys...'}</p> : null}

      <div className="columns-1 gap-4 md:columns-2 [&>*]:mb-4">
        <SectionCard icon={KeyRound} title={locale === 'zh-CN' ? '凭证概览' : 'Credential overview'}>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '密钥总数' : 'Total keys'}</p>
              <strong className="mt-2 block text-2xl text-[var(--text)]">{data?.length ?? 0}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '启用密钥' : 'Enabled'}</p>
              <strong className="mt-2 block text-2xl text-[var(--text)]">{enabledCount}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '停用密钥' : 'Disabled'}</p>
              <strong className="mt-2 block text-2xl text-[var(--text)]">{disabledCount}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '访问方式' : 'Auth mode'}</p>
              <strong className="mt-2 block text-sm text-[var(--text)]">Bearer Secret</strong>
            </div>
          </div>
        </SectionCard>

        <SectionCard icon={LockKeyhole} title={locale === 'zh-CN' ? '访问策略' : 'Access policy'}>
          <div className="space-y-3 text-sm leading-6 text-[var(--muted)]">
            <p>{locale === 'zh-CN' ? '每个密钥会生成独立 secret，用于客户端调用网关时的鉴权。' : 'Each key gets an independent secret used by clients when calling the gateway.'}</p>
            <p>{locale === 'zh-CN' ? '建议按业务系统拆分密钥，方便追踪、停用和轮换。' : 'Split keys by business system so they are easier to trace, disable, and rotate.'}</p>
          </div>
        </SectionCard>
      </div>

      <section className="rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '密钥列表' : 'Key list'}</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {locale === 'zh-CN' ? '使用与参考后台一致的紧凑卡片管理形式。' : 'Managed in a compact card layout aligned with the reference admin.'}
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {visibleData.map((item) => (
            <article key={item.id} className="rounded-[26px] border border-[var(--line)] bg-[var(--panel)] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <strong className="truncate text-[15px] text-[var(--text)]">{item.name}</strong>
                    <span className={item.enabled ? 'rounded-lg bg-[rgba(31,157,104,0.12)] px-2 py-1 text-[11px] text-[var(--success)]' : 'rounded-lg bg-[rgba(217,111,93,0.12)] px-2 py-1 text-[11px] text-[var(--danger)]'}>
                      {item.enabled ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}
                    </span>
                  </div>
                  <p className="mt-3 text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">secret</p>
                  <p className="mt-2 font-mono text-sm break-all text-[var(--text)]">{maskSecret(item.secret)}</p>
                </div>
                <div className="flex items-center gap-1 text-[var(--muted)]">
                  <button type="button" onClick={() => openEdit(item)} className="rounded-lg p-1.5 transition-colors hover:bg-[var(--panel-strong)] hover:text-[var(--text)]" title={locale === 'zh-CN' ? '编辑密钥' : 'Edit key'}>
                    <Pencil size={15} />
                  </button>
                  <button type="button" onClick={() => setDeleteTarget(item)} className="rounded-lg p-1.5 transition-colors hover:bg-[var(--panel-strong)] hover:text-[var(--danger)]" title={locale === 'zh-CN' ? '删除密钥' : 'Delete key'}>
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>

        {!isLoading && visibleData.length === 0 ? (
          <div className="mt-4 rounded-2xl border border-dashed border-[var(--line)] bg-[var(--panel)] px-5 py-8 text-center text-sm text-[var(--muted)]">
            {locale === 'zh-CN' ? '当前没有符合条件的密钥。' : 'No matching keys found.'}
          </div>
        ) : null}
      </section>

      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <AppDialogContent title={editingId ? (locale === 'zh-CN' ? '编辑密钥' : 'Edit key') : (locale === 'zh-CN' ? '新建密钥' : 'Create key')} description={locale === 'zh-CN' ? '创建或更新下游访问凭证。' : 'Create or update a downstream access credential.'}>
          <form className="grid gap-4" onSubmit={submit}>
            <input className={inputClassName()} placeholder={locale === 'zh-CN' ? '密钥名称' : 'Key name'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <label className="flex items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm text-[var(--text)]">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              {locale === 'zh-CN' ? '启用该密钥' : 'Enable this key'}
            </label>
            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-3">
              <button className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 py-2.5 text-sm text-[var(--text)]" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-xl bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white" type="submit">{editingId ? (locale === 'zh-CN' ? '保存密钥' : 'Save key') : (locale === 'zh-CN' ? '创建密钥' : 'Create key')}</button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除密钥' : 'Delete key'} description={locale === 'zh-CN' ? '删除后，使用该密钥的客户端将无法继续调用网关。' : 'Clients using this key will lose gateway access.'}>
          <div className="grid gap-5">
            <div className="rounded-2xl bg-[var(--panel)] p-4">
              <strong className="text-[var(--text)]">{deleteTarget?.name}</strong>
              <p className="mt-2 font-mono text-sm text-[var(--muted)] break-all">{deleteTarget?.secret}</p>
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
