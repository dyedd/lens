"use client"

import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Save, Search, Trash2, X, RefreshCcw, Info } from 'lucide-react'
import { ApiError, ModelPriceItem, ModelPriceListResponse, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { getModelGroupAvatar } from '@/lib/model-icons'
import { cn } from '@/lib/cn'

type ModelPriceDraft = Record<string, { input: string; output: string; cache_read: string; cache_write: string }>

function metricInputClassName() {
  return 'h-9 w-full rounded-xl border border-[rgba(37,99,235,0.12)] bg-[rgba(255,255,255,0.96)] px-3 text-[14px] font-medium text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function priceRowToneClassName(tone: 'input' | 'output') {
  if (tone === 'input') {
    return {
      surface: 'bg-[linear-gradient(180deg,rgba(229,239,255,0.96),rgba(223,234,255,0.88))]',
      badge: 'bg-[rgba(37,99,235,0.10)] text-[var(--accent)]',
    }
  }

  return {
    surface: 'bg-[linear-gradient(180deg,rgba(217,111,93,0.08),rgba(217,111,93,0.04))]',
    badge: 'bg-[rgba(217,111,93,0.14)] text-[var(--danger)]',
  }
}

function formatMoney(value: number) {
  if (value === 0) return '0'
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: value >= 1 ? 2 : 0,
    maximumFractionDigits: 4,
  }).format(value)
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

function PriceRow({
  locale,
  tone,
  primaryLabel,
  primaryValue,
  secondaryLabel,
  secondaryValue,
}: {
  locale: 'zh-CN' | 'en-US'
  tone: 'input' | 'output'
  primaryLabel: 'input' | 'output'
  primaryValue: number
  secondaryLabel: 'cache_read' | 'cache_write'
  secondaryValue: number
}) {
  const isInput = tone === 'input'
  const toneClassName = priceRowToneClassName(tone)

  return (
    <div className={cn('grid grid-cols-[minmax(0,1fr)_auto] items-end gap-3 rounded-[18px] px-3.5 py-2.5', toneClassName.surface)}>
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-[11px] font-medium text-[var(--muted)]">
          <span className={cn('inline-flex h-5 min-w-7 items-center justify-center rounded-full px-2 text-[10px] font-semibold uppercase tracking-[0.08em]', toneClassName.badge)}>{isInput ? 'IN' : 'OUT'}</span>
          <span>{metricLabel(primaryLabel, locale)}{locale === 'zh-CN' ? '价格' : ' Price'}</span>
        </div>
        <div className="mt-2 flex items-end gap-1 text-[var(--text)]">
          <span className="pb-0.5 text-[12px] font-medium leading-none text-[var(--muted)]">$</span>
          <span className="tabular-nums text-[20px] font-semibold leading-none">{formatMoney(primaryValue)}</span>
        </div>
      </div>

      <div className="min-w-[86px] text-right">
        <div className="text-[11px] font-medium text-[var(--muted)]">{metricLabel(secondaryLabel, locale)}</div>
        <div className="mt-1.5 flex items-end justify-end gap-1 text-[var(--text)]">
          <span className="text-[12px] font-medium leading-none text-[var(--muted)]">$</span>
          <span className="tabular-nums text-[15px] font-semibold leading-none">{formatMoney(secondaryValue)}</span>
        </div>
      </div>
    </div>
  )
}

function EditablePriceRow({
  locale,
  tone,
  primaryLabel,
  primaryValue,
  secondaryLabel,
  secondaryValue,
  onPrimaryChange,
  onSecondaryChange,
}: {
  locale: 'zh-CN' | 'en-US'
  tone: 'input' | 'output'
  primaryLabel: 'input' | 'output'
  primaryValue: string
  secondaryLabel: 'cache_read' | 'cache_write'
  secondaryValue: string
  onPrimaryChange: (value: string) => void
  onSecondaryChange: (value: string) => void
}) {
  const isInput = tone === 'input'
  const toneClassName = priceRowToneClassName(tone)

  return (
    <div className={cn('grid grid-cols-[minmax(0,1fr)_minmax(112px,0.8fr)] items-start gap-3 rounded-[18px] px-3.5 py-2.5', toneClassName.surface)}>
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-[11px] font-medium text-[var(--muted)]">
          <span className={cn('inline-flex h-5 min-w-7 items-center justify-center rounded-full px-2 text-[10px] font-semibold uppercase tracking-[0.08em]', toneClassName.badge)}>{isInput ? 'IN' : 'OUT'}</span>
          <span>{metricLabel(primaryLabel, locale)}{locale === 'zh-CN' ? '价格' : ' Price'}</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-[14px] font-medium text-[var(--muted)]">$</span>
          <input className={metricInputClassName()} value={primaryValue} onChange={(event) => onPrimaryChange(event.target.value)} />
        </div>
      </div>

      <div className="min-w-0">
        <div className="text-right text-[11px] font-medium text-[var(--muted)]">{metricLabel(secondaryLabel, locale)}</div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-[14px] font-medium text-[var(--muted)]">$</span>
          <input className={metricInputClassName()} value={secondaryValue} onChange={(event) => onSecondaryChange(event.target.value)} />
        </div>
      </div>
    </div>
  )
}

export function ModelPricesScreen() {
  const queryClient = useQueryClient()
  const { locale } = useI18n()
  const { data, isLoading } = useQuery({ queryKey: ['model-prices'], queryFn: () => apiRequest<ModelPriceListResponse>('/admin/model-prices') })
  const [drafts, setDrafts] = useState<ModelPriceDraft>({})
  const [busyKey, setBusyKey] = useState('')
  const [editingKey, setEditingKey] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [syncing, setSyncing] = useState(false)

  async function syncPrices() {
    setSyncing(true)
    setError('')
    setSaved('')
    try {
      await apiRequest<void>('/admin/model-price-sync-jobs', { method: 'POST' })
      setSaved(locale === 'zh-CN' ? '价格同步成功' : 'Prices synced successfully')
      await queryClient.invalidateQueries({ queryKey: ['model-prices'] })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '同步失败' : 'Failed to sync prices'))
    } finally {
      setSyncing(false)
    }
  }

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
      await apiRequest<ModelPriceItem>('/admin/model-prices/' + encodeURIComponent(item.model_key), {
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

  return (
    <section className="space-y-4">
      {typeof document !== 'undefined' && document.getElementById('header-portal') ? createPortal(
        <div className="flex flex-1 items-center justify-end gap-2">
          <div className="flex h-9 w-full max-w-sm items-center rounded-lg border border-[var(--line)] bg-[var(--panel-strong)] px-3 shadow-sm transition-colors focus-within:border-[var(--accent)]">
            <Search size={15} className="text-[var(--muted)]" />
            <input
              className="ml-2 h-full min-w-0 flex-1 bg-transparent text-[13px] text-[var(--text)] outline-none"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={locale === 'zh-CN' ? '搜索模型组' : 'Search groups'}
            />
            {search ? <button type="button" className="text-[var(--muted)] hover:text-[var(--text)]" onClick={() => setSearch('')}><X size={14} /></button> : null}
          </div>
          <div className="group relative">
            <button type="button" onClick={() => void syncPrices()} disabled={syncing} className="inline-flex h-9 items-center gap-2 rounded-lg bg-[var(--accent)] px-3.5 text-[13px] font-medium text-white shadow-sm transition-colors hover:opacity-90 disabled:opacity-60">
              <RefreshCcw size={15} className={syncing ? 'animate-spin' : ''} />
              <span className="hidden sm:inline">{syncing ? (locale === 'zh-CN' ? '同步中...' : 'Syncing...') : (locale === 'zh-CN' ? '重新同步配置' : 'Sync config')}</span>
            </button>
            <div className="pointer-events-none absolute right-0 top-full z-50 mt-1.5 w-max max-w-[200px] origin-top-right scale-95 opacity-0 transition-all group-hover:scale-100 group-hover:opacity-100">
              <div className="rounded-lg bg-[#1e293b] px-3 py-2.5 shadow-xl text-[12px] leading-tight text-white/90 text-center">
                {data?.last_synced_at ? (locale === 'zh-CN' ? `上次同步时间：\n${new Date(data.last_synced_at).toLocaleString('zh-CN')}` : `Last synced:\n${new Date(data.last_synced_at).toLocaleString()}`) : (locale === 'zh-CN' ? '未同步' : 'Never synced')}
              </div>
            </div>
          </div>
        </div>,
        document.getElementById('header-portal')!
      ) : null}

      <div className="grid gap-4 mt-2 md:grid-cols-2 xl:grid-cols-3">
        {filteredItems.map((item) => {
          const Avatar = getModelGroupAvatar(item.display_name)
          const editing = editingKey === item.model_key
          const protocolsText = item.protocols.map((protocol) => protocolLabel(protocol, locale)).join(' · ')

          return (
            <article key={item.model_key} className="rounded-[24px] border border-[rgba(37,99,235,0.12)] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(247,250,255,0.98))] p-3.5 shadow-[0_10px_24px_rgba(24,37,61,0.05)] transition-shadow hover:shadow-[0_14px_28px_rgba(24,37,61,0.08)]">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[18px] bg-[linear-gradient(180deg,rgba(234,241,255,0.95),rgba(225,235,255,0.92))]">
                      <Avatar size={28} />
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
                      'inline-flex h-8 w-8 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[rgba(37,99,235,0.06)] hover:text-[var(--text)]',
                      editing && 'bg-[rgba(37,99,235,0.08)] text-[var(--accent)]'
                    )}
                    onClick={() => setEditingKey((current) => current === item.model_key ? '' : item.model_key)}
                  >
                    {editing ? <X size={15} /> : <Pencil size={15} />}
                  </button>
                  <button
                    type="button"
                    title={locale === 'zh-CN' ? '清空价格' : 'Clear prices'}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-transparent text-[var(--muted)] transition hover:bg-[rgba(37,99,235,0.06)] hover:text-[var(--accent)]"
                    onClick={() => void clearPrice(item)}
                    disabled={busyKey === item.model_key}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              <div className="mt-3 space-y-2">
                {editing ? (
                  <EditablePriceRow
                    locale={locale}
                    tone="input"
                    primaryLabel="input"
                    primaryValue={drafts[item.model_key]?.input ?? ''}
                    secondaryLabel="cache_read"
                    secondaryValue={drafts[item.model_key]?.cache_read ?? ''}
                    onPrimaryChange={(value) => updateDraft(item.model_key, { input: value })}
                    onSecondaryChange={(value) => updateDraft(item.model_key, { cache_read: value })}
                  />
                ) : (
                  <PriceRow
                    locale={locale}
                    tone="input"
                    primaryLabel="input"
                    primaryValue={item.input_price_per_million}
                    secondaryLabel="cache_read"
                    secondaryValue={item.cache_read_price_per_million}
                  />
                )}

                {editing ? (
                  <EditablePriceRow
                    locale={locale}
                    tone="output"
                    primaryLabel="output"
                    primaryValue={drafts[item.model_key]?.output ?? ''}
                    secondaryLabel="cache_write"
                    secondaryValue={drafts[item.model_key]?.cache_write ?? ''}
                    onPrimaryChange={(value) => updateDraft(item.model_key, { output: value })}
                    onSecondaryChange={(value) => updateDraft(item.model_key, { cache_write: value })}
                  />
                ) : (
                  <PriceRow
                    locale={locale}
                    tone="output"
                    primaryLabel="output"
                    primaryValue={item.output_price_per_million}
                    secondaryLabel="cache_write"
                    secondaryValue={item.cache_write_price_per_million}
                  />
                )}

                {editing ? (
                  <div className="flex justify-end gap-2 px-1 pt-1">
                    <button className="inline-flex h-9 items-center justify-center rounded-xl border border-[rgba(37,99,235,0.12)] bg-[rgba(255,255,255,0.92)] px-4 text-sm text-[var(--text)] transition hover:bg-[rgba(255,255,255,0.98)]" type="button" onClick={() => setEditingKey('')}>
                      {locale === 'zh-CN' ? '取消' : 'Cancel'}
                    </button>
                    <button className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-[var(--accent)] px-4 text-sm font-medium text-white shadow-[0_10px_18px_rgba(37,99,235,0.16)] disabled:opacity-60" type="button" onClick={() => void savePrice(item)} disabled={busyKey === item.model_key}>
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
