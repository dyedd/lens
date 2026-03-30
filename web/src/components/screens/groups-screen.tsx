"use client"

import { FormEvent, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, ModelGroup, ModelGroupPayload, ProtocolKind, Provider, RoutingStrategy, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

type FormState = {
  name: string
  protocol: ProtocolKind
  strategy: RoutingStrategy
  provider_ids: string[]
  enabled: boolean
}

const emptyForm: FormState = { name: '', protocol: 'openai_chat', strategy: 'round_robin', provider_ids: [], enabled: true }

function toForm(item: ModelGroup): FormState {
  return { ...item }
}

function toPayload(form: FormState): ModelGroupPayload {
  return { ...form, name: form.name.trim() }
}

export function GroupsScreen() {
  const queryClient = useQueryClient()
  const { locale, t } = useI18n()
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const { data: groups, isLoading } = useQuery({ queryKey: ['groups'], queryFn: () => apiRequest<ModelGroup[]>('/model-groups') })
  const { data: providers } = useQuery({ queryKey: ['providers'], queryFn: () => apiRequest<Provider[]>('/providers') })

  const matchedProviders = useMemo(() => (providers ?? []).filter((item) => item.protocol === form.protocol), [providers, form.protocol])

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['groups'] }),
      queryClient.invalidateQueries({ queryKey: ['providers'] })
    ])
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      await apiRequest<ModelGroup>(editingId ? '/model-groups/' + editingId : '/model-groups', {
        method: editingId ? 'PUT' : 'POST',
        body: JSON.stringify(toPayload(form))
      })
      setEditingId(null)
      setForm(emptyForm)
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存模型组失败' : 'Failed to save group'))
    }
  }

  async function remove(id: string) {
    setBusyId(id)
    setError('')
    try {
      await apiRequest<void>('/model-groups/' + id, { method: 'DELETE' })
      if (editingId === id) {
        setEditingId(null)
        setForm(emptyForm)
      }
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
      <div className="rounded-[30px] border border-[var(--line)] bg-[linear-gradient(135deg,rgba(47,111,237,0.1),rgba(19,162,168,0.08))] p-6 md:p-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.22em] text-[var(--accent)]">{locale === 'zh-CN' ? '模型组' : 'Model groups'}</p>
            <h2 className="mt-3 text-4xl font-semibold leading-tight">{locale === 'zh-CN' ? '把外部模型名映射到一组可轮询的渠道。' : 'Map external model names to a routable pool of channels.'}</h2>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-[var(--muted)]">{locale === 'zh-CN' ? '模型组优先级高于渠道正则。适合同名模型做轮询、加权和故障切换。' : 'Model groups take precedence over provider regex rules.'}</p>
          </div>
          <button className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-2 text-sm shadow-[var(--shadow-sm)]" type="button" onClick={() => void refresh()}>{t.refresh}</button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[430px_minmax(0,1fr)]">
        <form className="grid gap-3 rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]" onSubmit={submit}>
          <div className="flex items-center justify-between gap-3">
            <strong>{editingId ? (locale === 'zh-CN' ? '编辑模型组' : 'Edit group') : (locale === 'zh-CN' ? '新建模型组' : 'Create group')}</strong>
            {editingId ? <button className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-2 text-sm" type="button" onClick={() => { setEditingId(null); setForm(emptyForm); setError('') }}>{locale === 'zh-CN' ? '取消' : 'Cancel'}</button> : null}
          </div>
          <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" placeholder={locale === 'zh-CN' ? '外部模型名' : 'External model name'} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as ProtocolKind, provider_ids: [] })}>
            <option value="openai_chat">OpenAI Chat</option>
            <option value="openai_responses">OpenAI Responses</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Gemini</option>
          </select>
          <select className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value as RoutingStrategy })}>
            <option value="round_robin">Round Robin</option>
            <option value="weighted">Weighted</option>
            <option value="failover">Failover</option>
          </select>
          <label className="flex items-center gap-3 rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3 text-sm text-[var(--muted)]">
            <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
            {locale === 'zh-CN' ? '启用模型组' : 'Enable group'}
          </label>
          <div className="grid gap-2 rounded-[24px] border border-[var(--line)] bg-[var(--panel-soft)] p-3">
            {matchedProviders.map((item) => (
              <label key={item.id} className="flex cursor-pointer items-center gap-3 rounded-2xl border border-[var(--line)] bg-white px-4 py-3 text-sm">
                <input type="checkbox" checked={form.provider_ids.includes(item.id)} onChange={() => toggleProvider(item.id)} />
                <span>{item.id} · {item.name}</span>
              </label>
            ))}
            {matchedProviders.length === 0 ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '当前协议下还没有可选渠道。' : 'No providers under this protocol.'}</p> : null}
          </div>
          {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
          <button className="rounded-2xl bg-[linear-gradient(135deg,#2f6fed,#1958d7)] px-5 py-3 text-white shadow-[0_16px_30px_rgba(47,111,237,0.24)]" type="submit">{editingId ? (locale === 'zh-CN' ? '保存模型组' : 'Save group') : (locale === 'zh-CN' ? '创建模型组' : 'Create group')}</button>
        </form>

        <div className="grid gap-3">
          {isLoading ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '正在加载模型组...' : 'Loading groups...'}</p> : null}
          {groups?.map((item) => (
            <div key={item.id} className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <strong className="text-lg">{item.name}</strong>
                    <span className={item.enabled ? 'rounded-full bg-[rgba(31,157,104,0.12)] px-3 py-1 text-xs text-[var(--success)]' : 'rounded-full bg-[rgba(192,58,76,0.12)] px-3 py-1 text-xs text-[var(--danger)]'}>{item.enabled ? (locale === 'zh-CN' ? '启用' : 'Enabled') : (locale === 'zh-CN' ? '停用' : 'Disabled')}</span>
                    <span className="rounded-full bg-[var(--panel-soft)] px-3 py-1 text-xs text-[var(--muted)]">{item.strategy}</span>
                  </div>
                  <p className="mt-3 text-sm text-[var(--muted)]">{item.protocol}</p>
                  <p className="mt-2 text-sm text-[var(--muted)]">{item.provider_ids.join(' -> ') || (locale === 'zh-CN' ? '未绑定渠道' : 'No providers')}</p>
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
