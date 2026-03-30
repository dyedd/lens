"use client"

import { FormEvent, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, LockKeyhole, Plus, ShieldCheck, Trash2 } from 'lucide-react'
import { ApiError, GatewayKey, GatewayKeyPayload, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { MetricCard } from '@/components/ui/metric-card'
import { PageHeader } from '@/components/ui/page-header'
import { SegmentedControl } from '@/components/ui/segmented-control'

type FormState = { name: string; enabled: boolean }
type ViewMode = 'cards' | 'list'

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

export function KeysScreen() {
  const queryClient = useQueryClient()
  const { locale, t } = useI18n()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<GatewayKey | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('cards')
  const { data, isLoading } = useQuery({ queryKey: ['gateway-keys'], queryFn: () => apiRequest<GatewayKey[]>('/gateway-keys') })

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
    <section className="grid gap-6">
      <PageHeader
        eyebrow={locale === 'zh-CN' ? '网关密钥' : 'Gateway keys'}
        title={locale === 'zh-CN' ? '为下游客户端发放访问 Lens 的凭证' : 'Issue client credentials for Lens access'}
        description={locale === 'zh-CN' ? '密钥页面改为卡片和列表双视图，编辑与删除都通过弹窗完成。' : 'The page now supports card and list views, with modal-based edit and delete flows.'}
        actions={
          <>
            <SegmentedControl value={viewMode} onValueChange={setViewMode} options={[{ value: 'cards', label: locale === 'zh-CN' ? '卡片' : 'Cards' }, { value: 'list', label: locale === 'zh-CN' ? '列表' : 'List' }]} />
            <button className="rounded-full border border-white/80 bg-white px-4 py-2.5 text-sm font-medium text-[var(--text)] shadow-[0_16px_30px_rgba(24,46,79,0.08)]" type="button" onClick={() => void refresh()}>{t.refresh}</button>
            <button className="inline-flex items-center gap-2 rounded-full bg-[linear-gradient(135deg,#2f6fed,#5a8fff)] px-4 py-2.5 text-sm font-medium text-white shadow-[0_18px_36px_rgba(47,111,237,0.28)]" type="button" onClick={openCreate}><Plus size={16} />{locale === 'zh-CN' ? '新增密钥' : 'New key'}</button>
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={KeyRound} label={locale === 'zh-CN' ? '密钥总数' : 'Keys'} value={data?.length ?? 0} tone="accent" />
        <MetricCard icon={ShieldCheck} label={locale === 'zh-CN' ? '启用密钥' : 'Enabled'} value={(data ?? []).filter((item) => item.enabled).length} />
        <MetricCard icon={LockKeyhole} label={locale === 'zh-CN' ? '停用密钥' : 'Disabled'} value={(data ?? []).filter((item) => !item.enabled).length} />
        <MetricCard icon={KeyRound} label={locale === 'zh-CN' ? '可见明文' : 'Visible secrets'} value={data?.length ?? 0} />
      </div>

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载网关密钥...' : 'Loading keys...'}</p> : null}

      {viewMode === 'cards' ? (
        <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
          {data?.map((item) => (
            <article key={item.id} className="rounded-[30px] border border-white/70 bg-[rgba(255,255,255,0.78)] p-5 shadow-[0_18px_44px_rgba(24,46,79,0.08)] backdrop-blur-[18px]">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="text-lg tracking-[-0.02em]">{item.name}</strong>
                    <span className={item.enabled ? 'rounded-full bg-[rgba(31,157,104,0.12)] px-3 py-1 text-xs text-[var(--success)]' : 'rounded-full bg-[rgba(192,58,76,0.12)] px-3 py-1 text-xs text-[var(--danger)]'}>{item.enabled ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="rounded-full border border-white/80 bg-white px-3 py-2 text-sm shadow-[0_10px_24px_rgba(24,46,79,0.08)]" type="button" onClick={() => openEdit(item)}>{locale === 'zh-CN' ? '编辑' : 'Edit'}</button>
                  <button className="rounded-full border border-[rgba(192,58,76,0.18)] bg-[rgba(192,58,76,0.08)] p-2 text-[var(--danger)]" type="button" onClick={() => setDeleteTarget(item)}><Trash2 size={16} /></button>
                </div>
              </div>
              <div className="mt-4 rounded-[24px] border border-white/70 bg-[rgba(247,249,253,0.84)] p-4">
                <p className="font-mono text-sm break-all text-[var(--muted)]">{item.secret}</p>
                <p className="mt-3 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{maskSecret(item.secret)}</p>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-[30px] border border-white/70 bg-[rgba(255,255,255,0.74)] shadow-[0_18px_44px_rgba(24,46,79,0.08)] backdrop-blur-[20px]">
          <div className="grid grid-cols-[minmax(0,1fr)_1.4fr_0.7fr_auto] gap-4 border-b border-white/70 px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">
            <span>{locale === 'zh-CN' ? '名称' : 'Name'}</span>
            <span>{locale === 'zh-CN' ? '密钥' : 'Secret'}</span>
            <span>{locale === 'zh-CN' ? '状态' : 'Status'}</span>
            <span>{locale === 'zh-CN' ? '操作' : 'Actions'}</span>
          </div>
          <div className="divide-y divide-white/60">
            {data?.map((item) => (
              <div key={item.id} className="grid grid-cols-[minmax(0,1fr)_1.4fr_0.7fr_auto] gap-4 px-5 py-4 text-sm text-[var(--text)]">
                <strong>{item.name}</strong>
                <span className="font-mono text-[var(--muted)]">{maskSecret(item.secret)}</span>
                <span className={item.enabled ? 'text-[var(--success)]' : 'text-[var(--danger)]'}>{item.enabled ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}</span>
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
        <AppDialogContent title={editingId ? (locale === 'zh-CN' ? '编辑密钥' : 'Edit key') : (locale === 'zh-CN' ? '新建密钥' : 'Create key')} description={locale === 'zh-CN' ? '创建或更新下游访问凭证。' : 'Create or update a downstream access credential.'}>
          <form className="grid gap-4" onSubmit={submit}>
            <input className="rounded-[22px] border border-[var(--line-strong)] bg-white/88 px-4 py-3 text-[var(--text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] outline-none transition focus:border-[var(--accent)] focus:bg-white" placeholder={locale === 'zh-CN' ? '密钥名称' : 'Key name'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <label className="flex items-center gap-3 rounded-[22px] border border-[var(--line-strong)] bg-white/88 px-4 py-3 text-sm text-[var(--muted)]">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              {locale === 'zh-CN' ? '启用该密钥' : 'Enable this key'}
            </label>
            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-3">
              <button className="rounded-full border border-white/80 bg-white px-4 py-2.5 text-sm font-medium text-[var(--text)] shadow-[0_10px_24px_rgba(24,46,79,0.08)]" type="button" onClick={() => setDialogOpen(false)}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button>
              <button className="rounded-full bg-[linear-gradient(135deg,#2f6fed,#5a8fff)] px-5 py-2.5 text-sm font-medium text-white shadow-[0_18px_36px_rgba(47,111,237,0.28)]" type="submit">{editingId ? (locale === 'zh-CN' ? '保存密钥' : 'Save key') : (locale === 'zh-CN' ? '创建密钥' : 'Create key')}</button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>

      <Dialog.Root open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent className="max-w-lg" title={locale === 'zh-CN' ? '确认删除密钥' : 'Delete key'} description={locale === 'zh-CN' ? '删除后，使用该密钥的客户端将无法继续调用网关。' : 'Clients using this key will lose gateway access.'}>
          <div className="grid gap-5">
            <div className="rounded-[24px] border border-white/70 bg-[rgba(247,249,253,0.86)] p-4">
              <strong>{deleteTarget?.name}</strong>
              <p className="mt-2 font-mono text-sm text-[var(--muted)]">{deleteTarget?.secret}</p>
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
