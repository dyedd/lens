"use client"

import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, RefreshCcw, Save, Trash2, X } from 'lucide-react'
import { ApiError, ModelPriceItem, ModelPriceListResponse, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { getModelGroupAvatar } from '@/lib/model-icons'
import { cn } from '@/lib/utils'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemFooter,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from '@/components/ui/item'
import { Input } from '@/components/ui/input'
import { ToolbarSearchInput } from '@/components/ui/toolbar-search-input'

type ModelPriceDraft = Record<string, { input: string; output: string; cache_read: string; cache_write: string }>

function metricInputClassName() {
  return 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm font-medium text-foreground outline-none transition focus:border-ring'
}

function priceRowToneClassName(tone: 'input' | 'output') {
  if (tone === 'input') {
    return {
      surface: 'border bg-muted/20',
      badge: 'bg-primary/10 text-primary',
    }
  }

  return {
    surface: 'border bg-muted/30',
    badge: 'bg-background text-muted-foreground',
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
    <div className={cn('grid grid-cols-[minmax(0,1fr)_auto] items-end gap-3 rounded-lg px-3.5 py-3', toneClassName.surface)}>
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <span className={cn('inline-flex h-5 min-w-7 items-center justify-center rounded-full px-2 text-xs font-semibold uppercase tracking-[0.08em]', toneClassName.badge)}>{isInput ? 'IN' : 'OUT'}</span>
          <span>{metricLabel(primaryLabel, locale)}{locale === 'zh-CN' ? '价格' : ' Price'}</span>
        </div>
        <div className="mt-2 flex items-end gap-1 text-foreground">
          <span className="pb-0.5 text-xs font-medium leading-none text-muted-foreground">$</span>
          <span className="tabular-nums text-lg font-semibold leading-none">{formatMoney(primaryValue)}</span>
        </div>
      </div>

      <div className="min-w-[86px] text-right">
        <div className="text-xs font-medium text-muted-foreground">{metricLabel(secondaryLabel, locale)}</div>
        <div className="mt-1.5 flex items-end justify-end gap-1 text-foreground">
          <span className="text-xs font-medium leading-none text-muted-foreground">$</span>
          <span className="tabular-nums text-sm font-semibold leading-none">{formatMoney(secondaryValue)}</span>
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
    <div className={cn('grid grid-cols-[minmax(0,1fr)_minmax(112px,0.8fr)] items-start gap-3 rounded-lg px-3.5 py-3', toneClassName.surface)}>
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <span className={cn('inline-flex h-5 min-w-7 items-center justify-center rounded-full px-2 text-xs font-semibold uppercase tracking-[0.08em]', toneClassName.badge)}>{isInput ? 'IN' : 'OUT'}</span>
          <span>{metricLabel(primaryLabel, locale)}{locale === 'zh-CN' ? '价格' : ' Price'}</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">$</span>
          <Input className={metricInputClassName()} value={primaryValue} onChange={(event) => onPrimaryChange(event.target.value)} />
        </div>
      </div>

      <div className="min-w-0">
        <div className="text-right text-xs font-medium text-muted-foreground">{metricLabel(secondaryLabel, locale)}</div>
        <div className="mt-2 flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">$</span>
          <Input className={metricInputClassName()} value={secondaryValue} onChange={(event) => onSecondaryChange(event.target.value)} />
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
  const [deleteTarget, setDeleteTarget] = useState<ModelPriceItem | null>(null)

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
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">{locale === 'zh-CN' ? '模型价格' : 'Model Prices'}</h1>
        <div className="flex items-center gap-2">
          <ToolbarSearchInput
            value={search}
            onChange={setSearch}
            onClear={() => setSearch('')}
            placeholder={locale === 'zh-CN' ? '搜索模型价格' : 'Search model prices'}
          />
          {data?.last_synced_at ? (
            <Badge variant="secondary" className="hidden lg:inline-flex px-2.5 py-1">
              {locale === 'zh-CN' ? `同步于 ${new Date(data.last_synced_at).toLocaleString('zh-CN')}` : `Synced ${new Date(data.last_synced_at).toLocaleString()}`}
            </Badge>
          ) : null}
          <div>
            <Button type="button" onClick={() => void syncPrices()} disabled={syncing}>
              <RefreshCcw data-icon="inline-start" className={syncing ? 'animate-spin' : ''} />
              <span className="hidden sm:inline">{syncing ? (locale === 'zh-CN' ? '同步中...' : 'Syncing...') : (locale === 'zh-CN' ? '重新同步配置' : 'Sync config')}</span>
            </Button>
          </div>
        </div>
      </div>

      {filteredItems.length ? (
        <div className="mt-2 rounded-xl border bg-card p-3">
          <ItemGroup className="gap-3">
            {filteredItems.map((item) => {
              const Avatar = getModelGroupAvatar(item.display_name)
              const editing = editingKey === item.model_key
              const protocolsText = item.protocols.map((protocol) => protocolLabel(protocol, locale)).join(' · ')

              return (
                <Item key={item.model_key} variant="outline" className="gap-4 px-4 py-4">
                  <ItemMedia variant="icon" className="flex size-11 rounded-xl bg-muted/40">
                    <Avatar size={28} />
                  </ItemMedia>
                  <ItemContent className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <ItemTitle className="truncate">{item.display_name}</ItemTitle>
                      <Badge variant="secondary" className="px-2.5 py-0.5 text-xs font-medium">
                        {item.protocols.length}
                        {locale === 'zh-CN' ? ' 个协议' : ' protocols'}
                      </Badge>
                    </div>
                    <ItemDescription className="mt-1 truncate">
                      {protocolsText || (locale === 'zh-CN' ? '未设置协议' : 'No protocol')}
                    </ItemDescription>

                    <ItemFooter className="mt-4 grid gap-2 lg:grid-cols-2">
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
                    </ItemFooter>

                    {editing ? (
                      <div className="mt-3 flex justify-end gap-2">
                        <Button variant="outline" type="button" onClick={() => setEditingKey('')}>
                          {locale === 'zh-CN' ? '取消' : 'Cancel'}
                        </Button>
                        <Button type="button" onClick={() => void savePrice(item)} disabled={busyKey === item.model_key}>
                          <Save data-icon="inline-start" />
                          {busyKey === item.model_key ? (locale === 'zh-CN' ? '保存中...' : 'Saving...') : (locale === 'zh-CN' ? '保存价格' : 'Save price')}
                        </Button>
                      </div>
                    ) : null}
                  </ItemContent>

                  <ItemActions className="ml-auto self-start">
                    <Button
                      type="button"
                      title={locale === 'zh-CN' ? '编辑价格' : 'Edit price'}
                      variant="ghost"
                      size="icon-sm"
                      className={cn(
                        'text-muted-foreground hover:text-foreground',
                        editing && 'bg-primary/10 text-primary'
                      )}
                      onClick={() => setEditingKey((current) => current === item.model_key ? '' : item.model_key)}
                    >
                      {editing ? <X size={15} /> : <Pencil size={15} />}
                    </Button>
                    <Button
                      type="button"
                      title={locale === 'zh-CN' ? '清空价格' : 'Clear prices'}
                      variant="ghost"
                      size="icon-sm"
                      className="text-muted-foreground hover:text-primary"
                      onClick={() => setDeleteTarget(item)}
                      disabled={busyKey === item.model_key}
                    >
                      <Trash2 size={15} />
                    </Button>
                  </ItemActions>
                </Item>
              )
            })}
          </ItemGroup>
        </div>
      ) : null}

      {!isLoading && !filteredItems.length ? (
        <div className="rounded-xl border border-dashed bg-card px-5 py-10 text-center text-sm text-muted-foreground">
          {search.trim()
            ? (locale === 'zh-CN' ? '没有匹配的模型组。' : 'No matching model groups.')
            : (locale === 'zh-CN' ? '当前还没有模型组价格。先创建模型组，再执行同步。' : 'No model group prices yet. Create model groups first, then sync.')}
        </div>
      ) : null}

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {saved ? <p className="text-sm text-primary">{saved}</p> : null}

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
        <AppDialogContent
          className="max-w-lg"
          title={locale === 'zh-CN' ? '清空模型价格' : 'Clear model prices'}
          description={deleteTarget
            ? (locale === 'zh-CN' ? `确认将 ${deleteTarget.display_name} 的价格全部清空为 0 吗？` : `Set all prices for ${deleteTarget.display_name} to 0?`)
            : ''}
        >
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>
              {locale === 'zh-CN' ? '取消' : 'Cancel'}
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                if (!deleteTarget) return
                void clearPrice(deleteTarget)
                setDeleteTarget(null)
              }}
            >
              {locale === 'zh-CN' ? '确认清空' : 'Clear prices'}
            </Button>
          </div>
        </AppDialogContent>
      </Dialog>
    </section>
  )
}
