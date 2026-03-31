"use client"

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Globe2, Languages, Plus, Save, ServerCog, ShieldCheck, Trash2 } from 'lucide-react'
import { ApiError, SettingItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

type Draft = { key: string; value: string }

function inputClassName() {
  return 'w-full rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)] focus:bg-[var(--panel-strong)]'
}

function SettingSection({
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

function KVRow({
  item,
  index,
  onChange,
  onRemove,
  locale
}: {
  item: Draft
  index: number
  onChange: (index: number, patch: Partial<Draft>) => void
  onRemove: (index: number) => void
  locale: 'zh-CN' | 'en-US'
}) {
  return (
    <div className="grid gap-3 rounded-3xl border border-[var(--line)] bg-[var(--panel)] p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)_auto]">
      <input className={inputClassName()} placeholder="key" value={item.key} onChange={(e) => onChange(index, { key: e.target.value })} />
      <input className={inputClassName()} placeholder="value" value={item.value} onChange={(e) => onChange(index, { value: e.target.value })} />
      <button
        className="inline-flex h-[46px] w-[46px] items-center justify-center rounded-2xl border border-[rgba(217,111,93,0.18)] bg-[rgba(217,111,93,0.08)] text-[var(--danger)] transition hover:bg-[rgba(217,111,93,0.12)]"
        type="button"
        onClick={() => onRemove(index)}
        title={locale === 'zh-CN' ? '删除配置' : 'Delete setting'}
      >
        <Trash2 size={16} />
      </button>
    </div>
  )
}

export function SettingsScreen() {
  const queryClient = useQueryClient()
  const { locale, setLocale } = useI18n()
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: () => apiRequest<SettingItem[]>('/settings') })
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  useEffect(() => {
    setDrafts((data ?? []).map((item) => ({ key: item.key, value: item.value })))
  }, [data])

  const nonEmptyCount = useMemo(() => drafts.filter((item) => item.key.trim() || item.value.trim()).length, [drafts])
  const blankCount = drafts.length - nonEmptyCount
  const previewKeys = useMemo(() => drafts.filter((item) => item.key.trim()).slice(0, 6), [drafts])

  function updateRow(index: number, patch: Partial<Draft>) {
    setDrafts((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
  }

  function removeRow(index: number) {
    setDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index))
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
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] text-[var(--text)]"
            type="button"
            onClick={() => void refresh()}
            title={locale === 'zh-CN' ? '刷新' : 'Refresh'}
          >
            <ServerCog size={16} />
          </button>
          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent)] text-white"
            type="button"
            onClick={() => setDrafts((current) => [...current, { key: '', value: '' }])}
            title={locale === 'zh-CN' ? '新增配置' : 'Add setting'}
          >
            <Plus size={16} />
          </button>
      </div>

      <div className="columns-1 gap-4 md:columns-2">
        <SettingSection
          icon={ShieldCheck}
          title={locale === 'zh-CN' ? '系统信息' : 'System info'}
          description={locale === 'zh-CN' ? '当前后台的基础运行形态。' : 'Basic runtime characteristics of the current admin.'}
        >
          <div className="grid gap-3 text-sm text-[var(--text)]">
            <div className="flex items-center justify-between rounded-2xl bg-[var(--panel)] px-4 py-3">
              <span className="text-[var(--muted)]">{locale === 'zh-CN' ? '数据库' : 'Database'}</span>
              <strong>SQLite</strong>
            </div>
            <div className="flex items-center justify-between rounded-2xl bg-[var(--panel)] px-4 py-3">
              <span className="text-[var(--muted)]">ORM</span>
              <strong>SQLAlchemy</strong>
            </div>
            <div className="flex items-center justify-between rounded-2xl bg-[var(--panel)] px-4 py-3">
              <span className="text-[var(--muted)]">{locale === 'zh-CN' ? '支持协议' : 'Protocols'}</span>
              <strong>OpenAI / Anthropic / Gemini</strong>
            </div>
          </div>
        </SettingSection>

        <SettingSection
          icon={Languages}
          title={locale === 'zh-CN' ? '界面偏好' : 'Appearance'}
          description={locale === 'zh-CN' ? '默认中文，也可以在这里快速切换管理台语言。' : 'Chinese is the default, and you can switch the admin language here.'}
        >
          <div className="grid gap-3">
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setLocale('zh-CN')}
                className={locale === 'zh-CN'
                  ? 'rounded-2xl bg-[var(--accent)] px-4 py-3 text-sm font-medium text-white'
                  : 'rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm text-[var(--text)]'}
              >
                简体中文
              </button>
              <button
                type="button"
                onClick={() => setLocale('en-US')}
                className={locale === 'en-US'
                  ? 'rounded-2xl bg-[var(--accent)] px-4 py-3 text-sm font-medium text-white'
                  : 'rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm text-[var(--text)]'}
              >
                English
              </button>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
              {locale === 'zh-CN'
                ? '语言偏好会保存在当前浏览器的本地存储中。'
                : 'The language preference is stored in local browser storage.'}
            </div>
          </div>
        </SettingSection>

        <SettingSection
          icon={Database}
          title={locale === 'zh-CN' ? '配置概览' : 'Config overview'}
          description={locale === 'zh-CN' ? '快速查看当前 key/value 配置规模。' : 'A quick view of the current key/value configuration set.'}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{locale === 'zh-CN' ? '总配置项' : 'Total items'}</p>
              <strong className="mt-3 block text-[28px] text-[var(--text)]">{drafts.length}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{locale === 'zh-CN' ? '有效配置' : 'Non-empty'}</p>
              <strong className="mt-3 block text-[28px] text-[var(--text)]">{nonEmptyCount}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{locale === 'zh-CN' ? '空白行' : 'Blank rows'}</p>
              <strong className="mt-3 block text-[28px] text-[var(--text)]">{blankCount}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-4">
              <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">{locale === 'zh-CN' ? '加载状态' : 'Load state'}</p>
              <strong className="mt-3 block text-[18px] text-[var(--text)]">{isLoading ? (locale === 'zh-CN' ? '加载中' : 'Loading') : (locale === 'zh-CN' ? '已就绪' : 'Ready')}</strong>
            </div>
          </div>
        </SettingSection>

        <SettingSection
          icon={Globe2}
          title={locale === 'zh-CN' ? '路由规则说明' : 'Routing notes'}
          description={locale === 'zh-CN' ? '当前聚合路由采用显式模型组优先，然后回退到渠道正则匹配。' : 'The gateway routes by exact model-group name first, then falls back to provider regex matching.'}
        >
          <div className="space-y-3 text-sm leading-6 text-[var(--muted)]">
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              {locale === 'zh-CN'
                ? '1. 先按模型组名称精确匹配，命中后使用该分组内的轮询、加权或故障转移策略。'
                : '1. Match the requested model against model-group names exactly, then use the configured strategy inside that group.'}
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              {locale === 'zh-CN'
                ? '2. 若没有命中模型组，再根据渠道上的正则规则顺序回退匹配，适合 `claude-opus-*` 这类前缀模型。'
                : '2. If no group matches, fall back to provider-side regex rules, which works well for patterns like `claude-opus-*`.'}
            </div>
          </div>
        </SettingSection>

        <SettingSection
          icon={ServerCog}
          title={locale === 'zh-CN' ? '配置键预览' : 'Key preview'}
          description={locale === 'zh-CN' ? '这里显示当前已保存配置中的前几个键。' : 'This previews the first few saved keys from the current configuration set.'}
        >
          <div className="flex flex-wrap gap-2">
            {previewKeys.length ? previewKeys.map((item) => (
              <span key={item.key} className="rounded-xl bg-[var(--panel)] px-3 py-2 text-sm text-[var(--text)]">
                {item.key}
              </span>
            )) : (
              <div className="rounded-2xl bg-[var(--panel)] px-4 py-3 text-sm text-[var(--muted)]">
                {locale === 'zh-CN' ? '当前还没有已保存的配置键。' : 'No saved configuration keys yet.'}
              </div>
            )}
          </div>
        </SettingSection>
      </div>

      <form className="rounded-[26px] border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]" onSubmit={submit}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '配置列表' : 'Configuration list'}</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {locale === 'zh-CN'
                ? '按 key/value 直接维护后端配置，保存时会过滤空 key。'
                : 'Edit backend configuration directly as key/value pairs. Empty keys are filtered on save.'}
            </p>
          </div>
          <button
            className="inline-flex h-11 items-center gap-2 rounded-full bg-[var(--accent)] px-4 text-sm font-medium text-white"
            type="button"
            onClick={() => setDrafts((current) => [...current, { key: '', value: '' }])}
          >
            <Plus size={16} />
            {locale === 'zh-CN' ? '新增' : 'Add'}
          </button>
        </div>

        <div className="mt-5 grid gap-3">
          {drafts.map((item, index) => (
            <KVRow key={item.key + '-' + index} item={item} index={index} onChange={updateRow} onRemove={removeRow} locale={locale} />
          ))}
          {!isLoading && drafts.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-[var(--line)] bg-[var(--panel)] px-5 py-10 text-center text-sm text-[var(--muted)]">
              {locale === 'zh-CN' ? '还没有配置项，可以先新增一行。' : 'No settings yet. Add your first row.'}
            </div>
          ) : null}
        </div>

        {error ? <p className="mt-4 text-sm text-[var(--danger)]">{error}</p> : null}
        {saved ? <p className="mt-4 text-sm text-[var(--success)]">{saved}</p> : null}

        <div className="mt-5 flex justify-end">
          <button className="inline-flex h-11 items-center gap-2 rounded-full bg-[var(--accent)] px-5 text-sm font-medium text-white" type="submit">
            <Save size={16} />
            {locale === 'zh-CN' ? '保存系统配置' : 'Save settings'}
          </button>
        </div>
      </form>
    </section>
  )
}
