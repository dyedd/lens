"use client"

import { FormEvent, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, Provider, ProtocolKind, ProviderPayload, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

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

const emptyForm: FormState = {
  name: '', protocol: 'openai_chat', base_url: '', api_key: '', model_name: '', status: 'enabled', weight: 1, priority: 100, model_patterns: ''
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

export function ChannelsScreen() {
  const queryClient = useQueryClient()
  const { locale, t } = useI18n()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const { data, isLoading } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['providers'] })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      await apiRequest<Provider>(editingId ? '/providers/' + editingId : '/providers', {
        method: editingId ? 'PUT' : 'POST',
        body: JSON.stringify(toPayload(form))
      })
      setEditingId(null)
      setForm(emptyForm)
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存渠道失败' : 'Failed to save channel'))
    }
  }

  async function remove(id: string) {
    setBusyId(id)
    setError('')
    try {
      await apiRequest<void>('/providers/' + id, { method: 'DELETE' })
      if (editingId === id) {
        setEditingId(null)
        setForm(emptyForm)
      }
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '删除渠道失败' : 'Failed to delete channel'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="grid gap-6">
      <div className="rounded-[30px] border border-[var(--line)] bg-[linear-gradient(135deg,rgba(47,111,237,0.1),rgba(19,162,168,0.08))] p-6 md:p-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.22em] text-[var(--accent)]">{locale === 'zh-CN' ? '渠道管理' : 'Channels'}</p>
            <h2 className="mt-3 text-4xl font-semibold leading-tight">{locale === 'zh-CN' ? '管理上游渠道池与模型匹配规则。' : 'Manage upstream channels and model matching rules.'}</h2>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-[var(--muted)]">{locale === 'zh-CN' ? '同协议内先匹配模型组，未命中时再按渠道正则回退。支持类似 claude-opus-4-6 的外部模型名正则承接。' : 'Model groups win first. Provider regex rules handle fallback within the same protocol family.'}</p>
          </div>
          <button className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-2 text-sm shadow-[var(--shadow-sm)]" type="button" onClick={() => void refresh()}>{t.refresh}</button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[430px_minmax(0,1fr)]">
        <form className="grid gap-3 rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]" onSubmit={submit}>
          <div className="flex items-center justify-between gap-3">
            <strong>{editingId ? (locale === 'zh-CN' ? '编辑渠道' : 'Edit channel') : (locale === 'zh-CN' ? '新建渠道' : 'Create channel')}</strong>
            {editingId ? <button className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-2 text-sm" type="button" onClick={() => { setEditingId(null); setForm(emptyForm); setError('') }}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button> : null}
          </div>
          <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" placeholder={locale === 'zh-CN' ? '渠道名称' : 'Channel name'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div className="grid gap-3 md:grid-cols-2">
            <select className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as ProtocolKind })}>
              {protocolOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <select className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as 'enabled' | 'disabled' })}>
              <option value="enabled">{locale === 'zh-CN' ? '启用' : 'Enabled'}</option>
              <option value="disabled">{locale === 'zh-CN' ? '停用' : 'Disabled'}</option>
            </select>
          </div>
          <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" placeholder="Base URL" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
          <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" placeholder="API Key" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
          <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" placeholder={locale === 'zh-CN' ? '模型覆写，可选' : 'Model override'} value={form.model_name} onChange={(e) => setForm({ ...form, model_name: e.target.value })} />
          <div className="grid grid-cols-2 gap-3">
            <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" type="number" min={1} placeholder={locale === 'zh-CN' ? '权重' : 'Weight'} value={form.weight} onChange={(e) => setForm({ ...form, weight: Number(e.target.value) || 1 })} />
            <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" type="number" min={1} placeholder={locale === 'zh-CN' ? '优先级' : 'Priority'} value={form.priority} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) || 1 })} />
          </div>
          <textarea className="min-h-28 rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" placeholder={locale === 'zh-CN' ? '每行一个模型正则' : 'One regex per line'} value={form.model_patterns} onChange={(e) => setForm({ ...form, model_patterns: e.target.value })} />
          {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
          <button className="rounded-2xl bg-[linear-gradient(135deg,#2f6fed,#1958d7)] px-5 py-3 text-white shadow-[0_16px_30px_rgba(47,111,237,0.24)]" type="submit">{editingId ? (locale === 'zh-CN' ? '保存渠道' : 'Save channel') : (locale === 'zh-CN' ? '创建渠道' : 'Create channel')}</button>
        </form>

        <div className="grid gap-3">
          {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载渠道...' : 'Loading channels...'}</p> : null}
          {data?.map((item) => (
            <div key={item.id} className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <strong className="text-lg">{item.name}</strong>
                    <span className={item.status === 'enabled' ? 'rounded-full bg-[rgba(31,157,104,0.12)] px-3 py-1 text-xs text-[var(--success)]' : 'rounded-full bg-[rgba(192,58,76,0.12)] px-3 py-1 text-xs text-[var(--danger)]'}>{item.status === 'enabled' ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}</span>
                    <span className="rounded-full bg-[var(--panel-soft)] px-3 py-1 text-xs text-[var(--muted)]">{protocolOptions.find((option) => option.value === item.protocol)?.label}</span>
                  </div>
                  <p className="mt-3 break-all text-sm text-[var(--muted)]">{item.base_url}</p>
                  <p className="mt-2 text-sm text-[var(--muted)]">{(item.model_patterns.length ? item.model_patterns : [item.model_name || (locale === 'zh-CN' ? '未设置模型条件' : 'No selector')]).join(' | ')}</p>
                  <p className="mt-2 text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '权重' : 'Weight'} {item.weight} · {locale === 'zh-CN' ? '优先级' : 'Priority'} {item.priority} · Key {maskKey(item.api_key)}</p>
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
