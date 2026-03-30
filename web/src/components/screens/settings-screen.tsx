"use client"

import { FormEvent, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, SettingItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

type Draft = { key: string; value: string }

export function SettingsScreen() {
  const queryClient = useQueryClient()
  const { locale, t } = useI18n()
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: () => apiRequest<SettingItem[]>('/settings') })
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  useEffect(() => {
    setDrafts((data ?? []).map((item) => ({ key: item.key, value: item.value })))
  }, [data])

  function updateRow(index: number, patch: Partial<Draft>) {
    setDrafts((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
  }

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['settings'] })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSaved('')
    try {
      const items = drafts.map((item) => ({ key: item.key.trim(), value: item.value.trim() })).filter((item) => item.key)
      await apiRequest<SettingItem[]>('/settings', { method: 'PUT', body: JSON.stringify({ items }) })
      setSaved(locale === 'zh-CN' ? '系统配置已保存' : 'Settings saved')
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存系统配置失败' : 'Failed to save settings'))
    }
  }

  return (
    <section className="grid gap-6">
      <div className="rounded-[30px] border border-[var(--line)] bg-[linear-gradient(135deg,rgba(47,111,237,0.1),rgba(19,162,168,0.08))] p-6 md:p-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.22em] text-[var(--accent)]">{locale === 'zh-CN' ? '系统设置' : 'Settings'}</p>
            <h2 className="mt-3 text-4xl font-semibold leading-tight">{locale === 'zh-CN' ? '维护后端运行参数与后台展示用配置。' : 'Maintain runtime and admin-facing settings.'}</h2>
          </div>
          <button className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-2 text-sm shadow-[var(--shadow-sm)]" type="button" onClick={() => void refresh()}>{t.refresh}</button>
        </div>
      </div>

      <form className="grid gap-3 rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]" onSubmit={submit}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <strong>{locale === 'zh-CN' ? '系统配置项' : 'System settings'}</strong>
          <button className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-2 text-sm" type="button" onClick={() => setDrafts((current) => [...current, { key: '', value: '' }])}>{locale === 'zh-CN' ? '新增一行' : 'Add row'}</button>
        </div>
        <div className="grid gap-3">
          {drafts.map((item, index) => (
            <div key={item.key + '-' + index} className="grid gap-3 rounded-[24px] border border-[var(--line)] bg-[var(--panel-soft)] p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
              <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" placeholder="key" value={item.key} onChange={(e) => updateRow(index, { key: e.target.value })} />
              <input className="rounded-2xl border border-[var(--line-strong)] bg-white px-4 py-3" placeholder="value" value={item.value} onChange={(e) => updateRow(index, { value: e.target.value })} />
              <button className="rounded-2xl border border-[rgba(192,58,76,0.2)] bg-[rgba(192,58,76,0.06)] px-4 py-2 text-sm text-[var(--danger)]" type="button" onClick={() => setDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index))}>{locale === 'zh-CN' ? '删除' : 'Remove'}</button>
            </div>
          ))}
          {!isLoading && drafts.length === 0 ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '还没有配置项，可以先新增一行。' : 'No settings yet. Add your first row.'}</p> : null}
        </div>
        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        {saved ? <p className="text-sm text-[var(--success)]">{saved}</p> : null}
        <button className="rounded-2xl bg-[linear-gradient(135deg,#2f6fed,#1958d7)] px-5 py-3 text-white shadow-[0_16px_30px_rgba(47,111,237,0.24)]" type="submit">{locale === 'zh-CN' ? '保存系统配置' : 'Save settings'}</button>
      </form>
    </section>
  )
}
