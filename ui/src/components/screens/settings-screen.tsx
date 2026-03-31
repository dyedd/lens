"use client"

import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Globe2, Languages, Plus, Save, ServerCog, ShieldCheck, Trash2 } from 'lucide-react'
import { ApiError, SettingItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

const GATEWAY_API_KEYS = 'gateway_api_keys'
const GATEWAY_REQUIRE_API_KEY = 'gateway_require_api_key'
const GATEWAY_API_KEY_HINT = 'gateway_api_key_hint'

type Draft = { key: string; value: string }

function inputClassName() {
  return 'h-10 w-full rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] px-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function SettingCard({
  icon: Icon,
  title,
  children,
  className = ''
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={'break-inside-avoid rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)] ' + className}>
      <h2 className="flex items-center gap-2 text-base font-semibold text-[var(--text)]">
        <Icon className="h-4 w-4 text-[var(--muted)]" />
        {title}
      </h2>
      <div className="mt-5">{children}</div>
    </section>
  )
}

function SettingRow({
  label,
  value,
  muted = false
}: {
  label: string
  value: React.ReactNode
  muted?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm font-medium text-[var(--text)]">{label}</span>
      <span className={muted ? 'text-sm text-[var(--muted)]' : 'text-sm text-[var(--text)]'}>{value}</span>
    </div>
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
    <div className="grid gap-2 rounded-2xl border border-[var(--line)] bg-[var(--panel)] p-3 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.2fr)_auto]">
      <input className={inputClassName()} placeholder="key" value={item.key} onChange={(e) => onChange(index, { key: e.target.value })} />
      <input className={inputClassName()} placeholder="value" value={item.value} onChange={(e) => onChange(index, { value: e.target.value })} />
      <button
        className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] text-[var(--muted)] transition-colors hover:text-[var(--danger)]"
        type="button"
        onClick={() => onRemove(index)}
        title={locale === 'zh-CN' ? '删除配置' : 'Delete setting'}
      >
        <Trash2 size={15} />
      </button>
    </div>
  )
}

function generateGatewayKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return 'sk-lens-' + crypto.randomUUID().replaceAll('-', '')
  }
  return 'sk-lens-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

function splitGatewayKeys(rawValue: string) {
  const result: string[] = []
  const seen = new Set<string>()
  for (const item of rawValue.replace(/\r/g, '\n').split('\n')) {
    const normalized = item.trim()
    if (!normalized || seen.has(normalized)) {
      continue
    }
    seen.add(normalized)
    result.push(normalized)
  }
  return result
}

function maskGatewayKey(value: string) {
  if (value.length <= 12) {
    return value
  }
  return value.slice(0, 7) + '...' + value.slice(-4)
}

export function SettingsScreen() {
  const queryClient = useQueryClient()
  const { locale, setLocale } = useI18n()
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: () => apiRequest<SettingItem[]>('/settings') })
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [gatewayKeys, setGatewayKeys] = useState<string[]>([])
  const [gatewayRequireApiKey, setGatewayRequireApiKey] = useState(true)
  const [gatewayHint, setGatewayHint] = useState('')
  const [newGatewayKey, setNewGatewayKey] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  useEffect(() => {
    const items = data ?? []
    const mapping = new Map(items.map((item) => [item.key, item.value]))
    setGatewayKeys(splitGatewayKeys(mapping.get(GATEWAY_API_KEYS) ?? ''))
    setGatewayRequireApiKey(!['0', 'false', 'no', 'off'].includes((mapping.get(GATEWAY_REQUIRE_API_KEY) ?? 'true').toLowerCase()))
    setGatewayHint(mapping.get(GATEWAY_API_KEY_HINT) ?? '')
    setNewGatewayKey('')
    setDrafts(
      items
        .filter((item) => item.key !== GATEWAY_API_KEYS && item.key !== GATEWAY_REQUIRE_API_KEY && item.key !== GATEWAY_API_KEY_HINT)
        .map((item) => ({ key: item.key, value: item.value }))
    )
  }, [data])

  const nonEmptyCount = useMemo(() => drafts.filter((item) => item.key.trim() || item.value.trim()).length, [drafts])
  const blankCount = drafts.length - nonEmptyCount
  const previewKeys = useMemo(() => drafts.filter((item) => item.key.trim()).slice(0, 8), [drafts])
  const gatewayHintText = gatewayHint.trim() || (locale === 'zh-CN' ? '未设置' : 'Not set')

  function updateRow(index: number, patch: Partial<Draft>) {
    setDrafts((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
  }

  function removeRow(index: number) {
    setDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index))
  }

  function appendGatewayKey(value: string) {
    const normalized = value.trim()
    if (!normalized) {
      return
    }
    setGatewayKeys((current) => current.includes(normalized) ? current : [...current, normalized])
  }

  function removeGatewayKey(value: string) {
    setGatewayKeys((current) => current.filter((item) => item !== value))
  }

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['settings'] })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSaved('')
    try {
      const items = [
        { key: GATEWAY_API_KEYS, value: gatewayKeys.join('\n') },
        { key: GATEWAY_REQUIRE_API_KEY, value: gatewayRequireApiKey ? 'true' : 'false' },
        { key: GATEWAY_API_KEY_HINT, value: gatewayHint.trim() },
        ...drafts.map((item) => ({ key: item.key.trim(), value: item.value.trim() })).filter((item) => item.key)
      ]
      await apiRequest<SettingItem[]>('/settings', { method: 'PUT', body: JSON.stringify({ items }) })
      setSaved(locale === 'zh-CN' ? '系统配置已保存' : 'Settings saved')
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (locale === 'zh-CN' ? '保存系统配置失败' : 'Failed to save settings'))
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] text-[var(--muted)] transition-colors hover:text-[var(--text)]"
          type="button"
          onClick={() => void refresh()}
          title={locale === 'zh-CN' ? '刷新' : 'Refresh'}
        >
          <ServerCog size={16} />
        </button>
        <button
          className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] text-[var(--muted)] transition-colors hover:text-[var(--text)]"
          type="button"
          onClick={() => setDrafts((current) => [...current, { key: '', value: '' }])}
          title={locale === 'zh-CN' ? '新增配置' : 'Add setting'}
        >
          <Plus size={16} />
        </button>
      </div>

      <div className="columns-1 gap-4 md:columns-2 [&>*]:mb-4">
        <SettingCard icon={ShieldCheck} title={locale === 'zh-CN' ? '服务 API 配置' : 'Gateway API config'}>
          <div className="space-y-4">
            <SettingRow label={locale === 'zh-CN' ? '鉴权模式' : 'Auth mode'} value={gatewayRequireApiKey ? (locale === 'zh-CN' ? '需要 API Key' : 'API key required') : (locale === 'zh-CN' ? '匿名访问' : 'Anonymous access')} muted />
            <SettingRow label={locale === 'zh-CN' ? '服务 API Key 数量' : 'Service API key count'} value={gatewayKeys.length} muted />
            <SettingRow label={locale === 'zh-CN' ? '调用提示' : 'Access hint'} value={gatewayHintText} muted />
            <p className="text-xs leading-6 text-[var(--muted)]">
              {locale === 'zh-CN'
                ? '这里配置的是访问当前服务 /v1/* 接口时使用的 API Key，不是渠道的上游密钥。'
                : 'These keys protect this service /v1/* access. They are not upstream provider keys.'}
            </p>
          </div>
        </SettingCard>

        <SettingCard icon={Languages} title={locale === 'zh-CN' ? '外观' : 'Appearance'}>
          <div className="space-y-4">
            <SettingRow
              label={locale === 'zh-CN' ? '语言' : 'Language'}
              value={
                <div className="inline-flex rounded-xl border border-[var(--line)] bg-[var(--panel)] p-1">
                  <button
                    type="button"
                    onClick={() => setLocale('zh-CN')}
                    className={locale === 'zh-CN' ? 'rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white' : 'rounded-lg px-3 py-1.5 text-xs text-[var(--muted)]'}
                  >
                    简体中文
                  </button>
                  <button
                    type="button"
                    onClick={() => setLocale('en-US')}
                    className={locale === 'en-US' ? 'rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white' : 'rounded-lg px-3 py-1.5 text-xs text-[var(--muted)]'}
                  >
                    English
                  </button>
                </div>
              }
            />
            <p className="text-xs leading-6 text-[var(--muted)]">
              {locale === 'zh-CN'
                ? '语言偏好会保存在当前浏览器本地。'
                : 'Language preference is stored in local browser storage.'}
            </p>
          </div>
        </SettingCard>

        <SettingCard icon={Database} title={locale === 'zh-CN' ? '配置概览' : 'Config overview'}>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '总配置项' : 'Total items'}</p>
              <strong className="mt-2 block text-2xl text-[var(--text)]">{drafts.length + 3}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '服务 API Key' : 'Service API keys'}</p>
              <strong className="mt-2 block text-2xl text-[var(--text)]">{gatewayKeys.length}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '有效配置' : 'Non-empty'}</p>
              <strong className="mt-2 block text-2xl text-[var(--text)]">{nonEmptyCount}</strong>
            </div>
            <div className="rounded-2xl bg-[var(--panel)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">{locale === 'zh-CN' ? '空白行' : 'Blank rows'}</p>
              <strong className="mt-2 block text-2xl text-[var(--text)]">{blankCount}</strong>
            </div>
          </div>
        </SettingCard>

        <SettingCard icon={Globe2} title={locale === 'zh-CN' ? '路由规则' : 'Routing'}>
          <div className="space-y-3 text-sm leading-6 text-[var(--muted)]">
            <p>{locale === 'zh-CN' ? '按模型组名精确匹配优先；未命中时，再使用渠道的正则规则回退匹配。' : 'Exact model-group match is used first. If it misses, provider regex rules are used as fallback.'}</p>
            <p>{locale === 'zh-CN' ? '服务自身的访问控制现在由设置页里的 API Key 统一管理。' : 'Service access control is now managed centrally by API keys in settings.'}</p>
          </div>
        </SettingCard>

        <SettingCard icon={ServerCog} title={locale === 'zh-CN' ? '配置键' : 'Config keys'}>
          <div className="flex flex-wrap gap-2">
            {previewKeys.length ? previewKeys.map((item) => (
              <span key={item.key} className="rounded-xl bg-[var(--panel)] px-3 py-2 text-xs text-[var(--text)]">
                {item.key}
              </span>
            )) : (
              <span className="text-sm text-[var(--muted)]">{locale === 'zh-CN' ? '当前没有额外配置键。' : 'No extra configuration keys yet.'}</span>
            )}
          </div>
        </SettingCard>
      </div>

      <form className="space-y-4" onSubmit={submit}>
        <section className="rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 className="text-base font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '服务 API Key' : 'Service API keys'}</h3>
              <p className="mt-1 text-sm text-[var(--muted)]">
                {locale === 'zh-CN'
                  ? '这些密钥用于调用当前服务的 /v1/* 接口。'
                  : 'These keys are used to call this service /v1/* endpoints.'}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                className="inline-flex h-9 items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-sm text-[var(--text)] transition-colors hover:bg-[var(--panel-soft)]"
                type="button"
                onClick={() => setNewGatewayKey(generateGatewayKey())}
              >
                <Plus size={15} />
                {locale === 'zh-CN' ? '生成密钥' : 'Generate key'}
              </button>
            </div>
          </div>

          <div className="mt-4 space-y-4">
            <label className="flex items-center gap-3 rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3 text-sm text-[var(--text)]">
              <input type="checkbox" checked={gatewayRequireApiKey} onChange={(e) => setGatewayRequireApiKey(e.target.checked)} />
              <span>{locale === 'zh-CN' ? '访问 /v1/* 时必须提供 API Key' : 'Require API key for /v1/* access'}</span>
            </label>

            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto]">
              <input
                className={inputClassName()}
                value={newGatewayKey}
                onChange={(e) => setNewGatewayKey(e.target.value)}
                placeholder={locale === 'zh-CN' ? '输入或生成新的服务 API Key' : 'Enter or generate a new service API key'}
              />
              <button
                className="inline-flex h-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 text-sm text-[var(--text)] transition-colors hover:bg-[var(--panel-soft)]"
                type="button"
                onClick={() => {
                  appendGatewayKey(newGatewayKey)
                  setNewGatewayKey('')
                }}
              >
                {locale === 'zh-CN' ? '加入列表' : 'Add key'}
              </button>
              <button
                className="inline-flex h-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 text-sm text-[var(--text)] transition-colors hover:bg-[var(--panel-soft)]"
                type="button"
                onClick={() => setNewGatewayKey('')}
              >
                {locale === 'zh-CN' ? '清空' : 'Clear'}
              </button>
            </div>

            <div className="grid gap-3">
              {gatewayKeys.length ? gatewayKeys.map((item) => (
                <div key={item} className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-4 py-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-[var(--text)]">{maskGatewayKey(item)}</div>
                    <div className="mt-1 truncate font-mono text-xs text-[var(--muted)]">{item}</div>
                  </div>
                  <button
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel-strong)] text-[var(--muted)] transition-colors hover:text-[var(--danger)]"
                    type="button"
                    onClick={() => removeGatewayKey(item)}
                    title={locale === 'zh-CN' ? '删除密钥' : 'Delete key'}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              )) : (
                <div className="rounded-2xl border border-dashed border-[var(--line)] bg-[var(--panel)] px-5 py-8 text-center text-sm text-[var(--muted)]">
                  {locale === 'zh-CN' ? '当前还没有服务 API Key。' : 'No service API keys yet.'}
                </div>
              )}
            </div>

            <input
              className={inputClassName()}
              value={gatewayHint}
              onChange={(e) => setGatewayHint(e.target.value)}
              placeholder={locale === 'zh-CN' ? '可选：展示给调用方的备注或用途提示' : 'Optional hint shown to callers or operators'}
            />
          </div>
        </section>

        <section className="rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold text-[var(--text)]">{locale === 'zh-CN' ? '额外系统配置' : 'Additional settings'}</h3>
              <p className="mt-1 text-sm text-[var(--muted)]">
                {locale === 'zh-CN' ? '保留少量扩展配置项，空 key 不会被保存。' : 'Keep a small set of extra key/value settings. Empty keys are filtered before save.'}
              </p>
            </div>
            <button
              className="inline-flex h-9 items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-sm text-[var(--text)] transition-colors hover:bg-[var(--panel-soft)]"
              type="button"
              onClick={() => setDrafts((current) => [...current, { key: '', value: '' }])}
            >
              <Plus size={15} />
              {locale === 'zh-CN' ? '新增' : 'Add'}
            </button>
          </div>

          <div className="mt-4 grid gap-3">
            {drafts.map((item, index) => (
              <KVRow key={item.key + '-' + index} item={item} index={index} onChange={updateRow} onRemove={removeRow} locale={locale} />
            ))}
            {!isLoading && drafts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[var(--line)] bg-[var(--panel)] px-5 py-8 text-center text-sm text-[var(--muted)]">
                {locale === 'zh-CN' ? '当前没有额外配置项。' : 'No additional settings yet.'}
              </div>
            ) : null}
          </div>
        </section>

        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        {saved ? <p className="text-sm text-[var(--success)]">{saved}</p> : null}

        <div className="flex justify-end">
          <button className="inline-flex h-10 items-center gap-2 rounded-xl bg-[var(--accent)] px-4 text-sm font-medium text-white" type="submit">
            <Save size={15} />
            {locale === 'zh-CN' ? '保存系统配置' : 'Save settings'}
          </button>
        </div>
      </form>
    </section>
  )
}
