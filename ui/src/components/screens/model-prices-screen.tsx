"use client"

import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, RefreshCcw, Save, Search, Trash2, X } from 'lucide-react'
import { ApiError, ModelPriceItem, ModelPriceListResponse, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { getModelGroupAvatar } from '@/lib/model-icons'
import { cn } from '@/lib/cn'

type ModelPriceDraft = Record<string, { input: string; output: string; cache_read: string; cache_write: string }>

function metricInputClassName() {
  return 'h-11 w-full rounded-2xl border border-[var(--line)] bg-[rgba(255,255,255,0.92)] px-3 text-[15px] font-medium text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function formatMoney(value: number) {
  if (value === 0) return '0'
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: value >= 1 ? 2 : 0,
    maximumFractionDigits: 4,
  }).format(value)
}

function formatSyncTime(value: string | null | undefined, locale: 'zh-CN' | 'en-US') {
  if (!value) {
    return locale === 'zh-CN' ? '未同步' : 'Never synced'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return locale === 'zh-CN' ? '未同步' : 'Never synced'
  }

  return new Intl.DateTimeFormat(locale, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function protocolLabel(protocol: string, locale: 'zh-CN' | 'en-US') {
  const labels: Record<string, { zh: string; en: string }> = {
    openai_chat: { zh: 'OpenAI Chat', en: 'OpenAI Chat' },
    openai_responses: { zh: 'OpenAI Responses', en: 'OpenAI Responses' },
    anthropic: { zh: 'Anthropic', en: 'Anthropic' },
    gemini: { zh: 'Gemini', en: 'Gemini' },
  }

  return labels[protocol]?.[locale === 'zh-CN' ? 'zh' : 'en'] ?? protocol
}

function metricLabel(key: 'input' | 'output' | 'cache_read' | 'cache_write', locale: 'zh-CN' | 'en-US') {
  const labels: Record<'input' | 'output' | 'cache_read' | 'cache_write', { zh: string; en: string }> = {
    input: { zh: '输入', en: 'Input' },
    output: { zh: '输出', en: 'Output' },
    cache_read: { zh: '缓存读取', en: 'Cache Read' },
    cache_write: { zh: '缓存写入', en: 'Cache Write' },
  }

  return labels[key][locale === 'zh-CN' ? 'zh' : 'en']
}

function MainPriceStat({ label, value, locale, tone }: { label: 'input' | 'output'; value: number; locale: 'zh-CN' | 'en-US'; tone: 'neutral' | 'accent' }) {
  const toneClassName = tone === 'accent'
    ? 'bg-[rgba(37,99,235,0.06)]'
    : 'bg-[rgba(255,255,255,0.78)]'

  return (
    <div className={cn('min-w-0 rounded-[20px] border border-[var(--line)] px-4 py-3.5', toneClassName)}>
      <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--muted)]">{metricLabel(label, locale)}</div>
      <div className="mt-2 flex items-end gap-1 text-[var(--text)]">
        <span className="pb-0.5 text-[13px] font-medium leading-none text-[var(--muted)]">$</span>
        <span className="tabular-nums text-[26px] font-semibold leading-none">{formatMoney(value)}</span>
      </div>
    </div>
  )
}

function CachePriceStat({ label, value, locale }: { label: 'cache_read' | 'cache_write'; value: number; locale: 'zh-CN' | 'en-US' }) {
  return (
    <div className="min-w-0 rounded-[18px] border border-[var(--line)] bg-[rgba(255,255,255,0.64)] px-4 py-3">
      <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--muted)]">{metricLabel(label, locale)}</div>
      <div className="mt-1.5 flex items-end gap-1 text-[var(--text)]">
        <span className="text-[12px] font-medium leading-none text-[var(--muted)]">$</span>
        <span className="tabular-nums text-[18px] font-semibold leading-none">{formatMoney(value)}</span>
      </div>
    </div>
  )
}

function EditablePriceField({
  label,
  value,
  locale,
  prominent,
  onChange,
}: {
  label: 'input' | 'output' | 'cache_read' | 'cache_write'
  value: string
  locale: 'zh-CN' | 'en-US'
  prominent?: boolean
  onChange: (value: string) => void
}) {
  return (
    <div className={cn(
      'min-w-0 rounded-[20px] border border-[var(--line)] bg-[rgba(255,255,255,0.78)] px-4 py-3',
      prominent && 'bg-[rgba(37,99,235,0.06)]'
    )}>
      <div className="text-[11px] font-medium text-[var(--muted)]">{locale === 'zh-CN' ? `${metricLabel(label, locale)} / 1M tokens` : `${metricLabel(label, locale)} / 1M tokens`}</div>
      <div className="mt-2.5 flex items-center gap-2">
        <span className="text-[15px] font-medium text-[var(--muted)]">$</span>
        <input className={metricInputClassName()} value={value} onChange={(event) => onChange(event.target.value)} />
      </div>
    </div>
  )
}

export function ModelPricesScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const { data, isLoading } = useQuery({ queryKey: ['model-prices'], queryFn: () => apiRequest<ModelPriceListResponse>('/model-prices') })
  const [drafts, setDrafts] = useState<ModelPriceDraft>({})
  const [busyKey, setBusyKey] = useState('')
  const [editingKey, setEditingKey] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  useEffect(() => {
    const nextDrafts: ModelPriceDraft = {}
    for (const item of data?.items ?? []) {
      nextDrafts[item.model_key] = {
        input: String(item.input_price_per_million),
        output: String(item.output_price_per_million),
        cache_read: String(item.cache_read_price_per_million),
        cache_write: String(item.cache_write_price_per_million),
      }
    }
    setDrafts(nextDrafts)
  }, [data])

  const filteredItems = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    if (!keyword) {
      return data?.items ?? []
    }
    return (data?.items ?? []).filter((item) => item.display_name.toLowerCase().includes(keyword))
  }, [data, search])

  function updateDraft(modelKey: string, patch: Partial<{ input: string; output: string; cache_read: string; cache_write: string }>) {
    setDrafts((current) => ({
      ...current,
      [modelKey]: {
        input: current[modelKey]?.input ?? '',
        output: current[modelKey]?.output ?? '',
        cache_read: current[modelKey]?.cache_read ?? '',
        cache_write: current[modelKey]?.cache_write ?? '',
        ...patch,
      },
    }))
  }

  async function savePrice(item: ModelPriceItem, override?: { input: number; output: number; cache_read: number; cache_write: number }) {
    const draft = drafts[item.model_key]
    const input = override?.input ?? Number(draft?.input ?? item.input_price_per_million)
    const output = override?.output ?? Number(draft?.output ?? item.output_price_per_million)
    const cacheRead = override?.cache_read ?? Number(draft?.cache_read ?? item.cache_read_price_per_million)
    const cacheWrite = override?.cache_write ?? Number(draft?.cache_write ?? item.cache_write_price_per_million)
    if (!Number.isFinite(input) || input < 0 || !Number.isFinite(output) || output < 0 || !Number.isFinite(cacheRead) || cacheRead < 0 || !Number.isFinite(cacheWrite) || cacheWrite < 0) {
      setError(locale === 'zh-CN' ? '价格必须是大于等于 0 的数字' : 'Prices must be numbers greater than or equal to 0')
      return
    }

    setBusyKey(item.model_key)
    setError('')
    setSaved('')
    try {
      await apiRequest<ModelPriceItem>('/model-prices/' + encodeURIComponent(item.model_key), {
        method: 'PUT',
        body: JSON.stringify({
          model_key: item.model_key,
          display_name: item.display_name,
          input_price_per_million: input,
          output_price_per_million: output,
          cache_read_price_per_million: cacheRead,
          cache_write_price_per_million: cacheWrite,
        }),
      })
      setSaved(locale === 'zh-CN' ? '模型价格已保存' : 'Model price saved')
      setEditingKey('')
      await queryClient.invalidateQueries({ queryKey: ['model-prices'] })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存模型价格失败' : 'Failed to save model price'))
    } finally {
      setBusyKey('')
    }
  }

  async function clearPrice(item: ModelPriceItem) {
    const confirmed = window.confirm(locale === 'zh-CN' ? `确认清空 ${item.display_name} 的价格吗？` : `Clear all prices for ${item.display_name}?`)
    if (!confirmed) {
      return
    }

    setDrafts((current) => ({
      ...current,
      [item.model_key]: {
        input: '0',
        output: '0',
        cache_read: '0',
        cache_write: '0',
      },
    }))
    await savePrice(item, { input: 0, output: 0, cache_read: 0, cache_write: 0 })
  }

  async function syncPrices() {
    setBusyKey('__sync__')
    setError('')
    setSaved('')
    try {
      await apiRequest<ModelPriceListResponse>('/model-prices/sync', { method: 'POST' })
      setSaved(locale === 'zh-CN' ? '模型价格已同步' : 'Model prices synced')
      await queryClient.invalidateQueries({ queryKey: ['model-prices'] })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '同步模型价格失败' : 'Failed to sync model prices'))
    } finally {
      setBusyKey('')
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-[12px] text-[var(--muted)]">
          <span className="rounded-full bg-[var(--panel-strong)] px-3 py-1.5 font-medium text-[var(--text)] shadow-[var(--shadow-sm)]">{data?.items.length ?? 0}</span>
          <span>{locale === 'zh-CN' ? '模型组价格' : 'Model group prices'}</span>
          <span className="hidden sm:inline">·</span>
          <span>{locale === 'zh-CN' ? `最近同步 ${formatSyncTime(data?.last_synced_at, locale)}` : `Last sync ${formatSyncTime(data?.last_synced_at, locale)}`}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="hidden h-9 items-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 md:flex">
            <Search size={15} className="text-[var(--muted)]" />
            <input
              className="ml-2 w-44 bg-transparent text-[13px] text-[var(--text)] outline-none"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={locale === 'zh-CN' ? '搜索模型组' : 'Search groups'}
            />
          </div>

          <button
            className="inline-flex h-9 items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 text-[13px] font-medium text-[var(--text)] transition hover:text-[var(--text)] disabled:opacity-60"
            type="button"
            onClick={() => void syncPrices()}
            disabled={busyKey === '__sync__'}
          >
            <RefreshCcw size={15} className={cn(busyKey === '__sync__' && 'animate-spin')} />
            <span>{busyKey === '__sync__' ? (locale === 'zh-CN' ? '同步中...' : 'Syncing...') : (locale === 'zh-CN' ? '同步价格' : 'Sync prices')}</span>
          </button>
        </div>

        <div className="flex h-9 w-full items-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 md:hidden">
          <Search size={15} className="text-[var(--muted)]" />
          <input
            className="ml-2 min-w-0 flex-1 bg-transparent text-[13px] text-[var(--text)] outline-none"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={locale === 'zh-CN' ? '搜索模型组' : 'Search groups'}
          />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filteredItems.map((item) => {
          const Avatar = getModelGroupAvatar(item.display_name)
          const editing = editingKey === item.model_key
          const protocolsText = item.protocols.map((protocol) => protocolLabel(protocol, locale)).join(' · ')

          return (
            <article key={item.model_key} className="rounded-[28px] border border-[var(--line)] bg-[var(--panel-strong)] p-4 shadow-[var(--shadow-sm)] transition-shadow hover:shadow-[0_14px_32px_rgba(24,37,61,0.08)]">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[var(--panel-soft)] ring-1 ring-[var(--line)]">
                      <Avatar size={30} />
                    </span>

                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[15px] font-semibold text-[var(--text)]">{item.display_name}</div>
                      <div className="mt-1 truncate text-xs text-[var(--muted)]">{protocolsText || (locale === 'zh-CN' ? '未设置协议' : 'No protocol')}</div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    title={locale === 'zh-CN' ? '编辑价格' : 'Edit price'}
                    className={cn(
                      'inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--text)]',
                      editing && 'bg-[var(--panel)] text-[var(--accent)]'
                    )}
                    onClick={() => setEditingKey((current) => current === item.model_key ? '' : item.model_key)}
                  >
                    {editing ? <X size={15} /> : <Pencil size={15} />}
                  </button>
                  <button
                    type="button"
                    title={locale === 'zh-CN' ? '清空价格' : 'Clear prices'}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-transparent text-[var(--danger)] transition hover:bg-[rgba(217,111,93,0.08)]"
                    onClick={() => void clearPrice(item)}
                    disabled={busyKey === item.model_key}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              <div className="mt-4 rounded-[24px] bg-[var(--panel-soft)] p-2.5 ring-1 ring-[var(--line)]">
                <div className="grid grid-cols-2 gap-2.5">
                  {editing ? (
                    <EditablePriceField locale={locale} label="input" value={drafts[item.model_key]?.input ?? ''} prominent onChange={(value) => updateDraft(item.model_key, { input: value })} />
                  ) : (
                    <MainPriceStat locale={locale} label="input" value={item.input_price_per_million} tone="accent" />
                  )}

                  {editing ? (
                    <EditablePriceField locale={locale} label="output" value={drafts[item.model_key]?.output ?? ''} prominent={false} onChange={(value) => updateDraft(item.model_key, { output: value })} />
                  ) : (
                    <MainPriceStat locale={locale} label="output" value={item.output_price_per_million} tone="neutral" />
                  )}
                </div>

                <div className="mt-2.5 grid grid-cols-2 gap-2.5">
                  {editing ? (
                    <EditablePriceField locale={locale} label="cache_read" value={drafts[item.model_key]?.cache_read ?? ''} onChange={(value) => updateDraft(item.model_key, { cache_read: value })} />
                  ) : (
                    <CachePriceStat locale={locale} label="cache_read" value={item.cache_read_price_per_million} />
                  )}

                  {editing ? (
                    <EditablePriceField locale={locale} label="cache_write" value={drafts[item.model_key]?.cache_write ?? ''} onChange={(value) => updateDraft(item.model_key, { cache_write: value })} />
                  ) : (
                    <CachePriceStat locale={locale} label="cache_write" value={item.cache_write_price_per_million} />
                  )}
                </div>

                {editing ? (
                  <div className="mt-3 flex justify-end gap-2 border-t border-[var(--line)] px-1 pt-3">
                    <button className="inline-flex h-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 text-sm text-[var(--text)] transition hover:bg-[var(--panel-soft)]" type="button" onClick={() => setEditingKey('')}>
                      {locale === 'zh-CN' ? '取消' : 'Cancel'}
                    </button>
                    <button className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[var(--accent)] px-4 text-sm font-medium text-white disabled:opacity-60" type="button" onClick={() => void savePrice(item)} disabled={busyKey === item.model_key}>
                      <Save size={15} />
                      {busyKey === item.model_key ? (locale === 'zh-CN' ? '保存中...' : 'Saving...') : (locale === 'zh-CN' ? '保存价格' : 'Save price')}
                    </button>
                  </div>
                ) : null}
              </div>
            </article>
          )
        })}
      </div>

      {!isLoading && !filteredItems.length ? (
        <div className="rounded-[28px] border border-dashed border-[var(--line)] bg-[var(--panel-strong)] px-5 py-10 text-center text-sm text-[var(--muted)]">
          {search.trim()
            ? (locale === 'zh-CN' ? '没有匹配的模型组。' : 'No matching model groups.')
            : (locale === 'zh-CN' ? '当前还没有模型组价格。先创建模型组，再执行同步。' : 'No model group prices yet. Create model groups first, then sync.')}
        </div>
      ) : null}

      {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
      {saved ? <p className="text-sm text-[var(--success)]">{saved}</p> : null}
    </section>
  )
}
