"use client"

import { FormEvent, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, GatewayKey, GatewayKeyPayload, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

type FormState = { name: string; enabled: boolean }

const emptyForm: FormState = { name: 'default-client', enabled: true }

function toForm(item: GatewayKey): FormState {
  return { name: item.name, enabled: item.enabled }
}

function toPayload(form: FormState): GatewayKeyPayload {
  return { name: form.name.trim(), enabled: form.enabled }
}

export function KeysScreen() {
  const queryClient = useQueryClient()
  const { locale, t } = useI18n()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const { data, isLoading } = useQuery({ queryKey: ['gateway-keys'], queryFn: () => apiRequest<GatewayKey[]>('/gateway-keys') })

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['gateway-keys'] })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      await apiRequest<GatewayKey>(editingId ? '/gateway-keys/' + editingId : '/gateway-keys', {
        method: editingId ? 'PUT' : 'POST',
        body: JSON.stringify(toPayload(form))
      })
      setEditingId(null)
      setForm(emptyForm)
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存网关密钥失败' : 'Failed to save key'))
    }
  }

  async function remove(id: string) {
    setBusyId(id)
    setError('')
    try {
      await apiRequest<void>('/gateway-keys/' + id, { method: 'DELETE' })
      if (editingId === id) {
        setEditingId(null)
        setForm(emptyForm)
      }
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除网关密钥失败' : 'Failed to delete key'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="grid gap-6">
      <div className="rounded-[30px] border border-[var(--line)] bg-[linear-gradient(135deg,rgba(47,111,237,0.1),rgba(19,162,168,0.08))] p-6 md:p-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.22em] text-[var(--accent)]">{locale === 'zh-CN' ? '网关密钥' : 'Gateway keys'}</p>
            <h2 className="mt-3 text-4xl font-semibold leading-tight">{locale === 'zh-CN' ? '为下游客户端发放访问 Lens 的密钥。' : 'Issue access keys for downstream clients.'}</h2>
          </div>
          <button className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-2 text-sm shadow-[var(--shadow-sm)]" type="button" onClick={() => void refresh()}>{t.refresh}</button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[430px_minmax(0,1fr)]">
        <form className="grid gap-3 rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]" onSubmit={submit}>
          <div className="flex items-center justify-between gap-3">
            <strong>{editingId ? (locale === 'zh-CN' ? '编辑密钥' : 'Edit key') : (locale === 'zh-CN' ? '新建密钥' : 'Create key')}</strong>
            {editingId ? <button className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-2 text-sm" type="button" onClick={() => { setEditingId(null); setForm(emptyForm); setError('') }}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button> : null}
          </div>
          <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" placeholder={locale === 'zh-CN' ? '密钥名称' : 'Key name'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <label className="flex items-center gap-3 rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3 text-sm text-[var(--muted)]">
            <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
            {locale === 'zh-CN' ? '启用该密钥' : 'Enable this key'}
          </label>
          {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
          <button className="rounded-2xl bg-[linear-gradient(135deg,#2f6fed,#1958d7)] px-5 py-3 text-white shadow-[0_16px_30px_rgba(47,111,237,0.24)]" type="submit">{editingId ? (locale === 'zh-CN' ? '保存密钥' : 'Save key') : (locale === 'zh-CN' ? '创建密钥' : 'Create key')}</button>
        </form>

        <div className="grid gap-3">
          {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载网关密钥...' : 'Loading keys...'}</p> : null}
          {data?.map((item) => (
            <div key={item.id} className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <strong className="text-lg">{item.name}</strong>
                    <span className={item.enabled ? 'rounded-full bg-[rgba(31,157,104,0.12)] px-3 py-1 text-xs text-[var(--success)]' : 'rounded-full bg-[rgba(192,58,76,0.12)] px-3 py-1 text-xs text-[var(--danger)]'}>{item.enabled ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}</span>
                  </div>
                  <p className="mt-3 break-all font-mono text-sm text-[var(--muted)]">{item.secret}</p>
                </div>
                <div className="flex gap-2">
                  <button className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-2 text-sm" type="button" onClick={() => { setEditingId(item.id); setForm(toForm(item)); setError('') }}>{locale === 'zh-CN' ? '编辑' : 'Edit'}</button>
                  <button className="rounded-2xl border border-[rgba(192,58,76,0.2)] bg-[rgba(192,58,76,0.06)] px-4 py-2 text-sm text-[var(--danger)]" type="button" onClick={() => void remove(item.id)} disabled={busyId === item.id}>{busyId === item.id ? (locale === 'zh-CN' ? '删除中...' : 'Deleting...') : (locale === 'zh-CN' ? '删除' : 'Delete')}</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
