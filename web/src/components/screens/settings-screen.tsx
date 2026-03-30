"use client"

import { FormEvent, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Plus, Settings2, SlidersHorizontal, Trash2 } from 'lucide-react'
import { ApiError, SettingItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { MetricCard } from '@/components/ui/metric-card'
import { PageHeader } from '@/components/ui/page-header'

type Draft = { key: string; value: string }

function inputClassName() {
  return 'rounded-[22px] border border-[var(--line-strong)] bg-white/88 px-4 py-3 text-[var(--text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] outline-none transition focus:border-[var(--accent)] focus:bg-white'
}

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
      <PageHeader
        eyebrow={locale === 'zh-CN' ? '系统设置' : 'Settings'}
        title={locale === 'zh-CN' ? '维护后端运行参数与后台展示配置' : 'Maintain runtime and admin-facing settings'}
        description={locale === 'zh-CN' ? '设置页保持分块式编辑，适合批量维护 key/value 配置。' : 'The settings surface stays block-based and optimized for batch key/value editing.'}
        actions={
          <>
            <button className="inline-flex items-center gap-2 rounded-full border border-white/80 bg-white px-4 py-2.5 text-sm font-medium text-[var(--text)] shadow-[0_16px_30px_rgba(24,46,79,0.08)]" type="button" onClick={() => void refresh()}><SlidersHorizontal size={16} />{t.refresh}</button>
            <button className="inline-flex items-center gap-2 rounded-full bg-[linear-gradient(135deg,#2f6fed,#5a8fff)] px-4 py-2.5 text-sm font-medium text-white shadow-[0_18px_36px_rgba(47,111,237,0.28)]" type="button" onClick={() => setDrafts((current) => [...current, { key: '', value: '' }])}><Plus size={16} />{locale === 'zh-CN' ? '新增配置' : 'Add setting'}</button>
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Settings2} label={locale === 'zh-CN' ? '配置项' : 'Settings'} value={drafts.length} tone="accent" />
        <MetricCard icon={Database} label={locale === 'zh-CN' ? '已保存配置' : 'Persisted'} value={data?.length ?? 0} />
        <MetricCard icon={Settings2} label={locale === 'zh-CN' ? '待编辑行' : 'Draft rows'} value={drafts.filter((item) => item.key || item.value).length} />
        <MetricCard icon={Database} label={locale === 'zh-CN' ? '空白行' : 'Blank rows'} value={drafts.filter((item) => !item.key && !item.value).length} />
      </div>

      <form className="grid gap-4 rounded-[32px] border border-white/70 bg-[rgba(255,255,255,0.78)] p-5 shadow-[0_18px_44px_rgba(24,46,79,0.08)] backdrop-blur-[18px]" onSubmit={submit}>
        <div className="grid gap-3">
          {drafts.map((item, index) => (
            <div key={item.key + '-' + index} className="grid gap-3 rounded-[24px] border border-white/70 bg-[rgba(247,249,253,0.86)] p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
              <input className={inputClassName()} placeholder="key" value={item.key} onChange={(e) => updateRow(index, { key: e.target.value })} />
              <input className={inputClassName()} placeholder="value" value={item.value} onChange={(e) => updateRow(index, { value: e.target.value })} />
              <button className="inline-flex items-center justify-center rounded-[22px] border border-[rgba(192,58,76,0.18)] bg-[rgba(192,58,76,0.08)] px-4 py-3 text-[var(--danger)]" type="button" onClick={() => setDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={16} /></button>
            </div>
          ))}
          {!isLoading && drafts.length === 0 ? <p className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '还没有配置项，可以先新增一行。' : 'No settings yet. Add your first row.'}</p> : null}
        </div>
        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        {saved ? <p className="text-sm text-[var(--success)]">{saved}</p> : null}
        <div className="flex justify-end">
          <button className="rounded-full bg-[linear-gradient(135deg,#2f6fed,#5a8fff)] px-5 py-2.5 text-sm font-medium text-white shadow-[0_18px_36px_rgba(47,111,237,0.28)]" type="submit">{locale === 'zh-CN' ? '保存系统配置' : 'Save settings'}</button>
        </div>
      </form>
    </section>
  )
}
