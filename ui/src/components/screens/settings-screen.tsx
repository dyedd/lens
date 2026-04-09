"use client"

import Image from 'next/image'
import { FormEvent, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, CircleAlert, Copy, ImageIcon, Info, KeyRound, Palette, RotateCcw, Save, ServerCog, ShieldCheck, Trash2, UserRound } from 'lucide-react'
import { Dialog, AppDialogContent } from '@/components/ui/dialog'
import { useToast } from '@/components/ui/toast'
import { ApiError, type AdminPasswordChangePayload, type AdminProfile, type AppInfo, type ModelPriceListResponse, type SettingItem, apiRequest } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

const GATEWAY_API_KEYS = 'gateway_api_keys'
const GATEWAY_API_KEY_HINT = 'gateway_api_key_hint'
const PROXY_URL = 'proxy_url'
const STATS_SAVE_INTERVAL = 'stats_save_interval'
const CORS_ALLOW_ORIGINS = 'cors_allow_origins'
const RELAY_LOG_KEEP_ENABLED = 'relay_log_keep_enabled'
const RELAY_LOG_KEEP_PERIOD = 'relay_log_keep_period'
const CIRCUIT_BREAKER_THRESHOLD = 'circuit_breaker_threshold'
const CIRCUIT_BREAKER_COOLDOWN = 'circuit_breaker_cooldown'
const CIRCUIT_BREAKER_MAX_COOLDOWN = 'circuit_breaker_max_cooldown'
const SITE_NAME = 'site_name'
const SITE_LOGO_URL = 'site_logo_url'

type Locale = 'zh-CN' | 'en-US'

type FieldSpec = {
  key: string
  value: string
}

type DraftState = {
  proxyUrl: string
  statsSaveInterval: string
  corsAllowOrigins: string
  relayLogKeepEnabled: boolean
  relayLogKeepPeriod: string
  circuitBreakerThreshold: string
  circuitBreakerCooldown: string
  circuitBreakerMaxCooldown: string
  siteName: string
  siteLogoUrl: string
}

const EMPTY_DRAFT: DraftState = {
  proxyUrl: '',
  statsSaveInterval: '60',
  corsAllowOrigins: '*',
  relayLogKeepEnabled: true,
  relayLogKeepPeriod: '7',
  circuitBreakerThreshold: '3',
  circuitBreakerCooldown: '60',
  circuitBreakerMaxCooldown: '600',
  siteName: 'Lens',
  siteLogoUrl: '',
}

function inputClassName() {
  return 'h-10 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function textareaClassName() {
  return 'min-h-[92px] w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm text-[var(--text)] outline-none transition focus:border-[var(--accent)]'
}

function cardClassName() {
  return 'rounded-3xl border border-[var(--line)] bg-[var(--panel-strong)] p-5 shadow-[var(--shadow-sm)]'
}

function titleForLocale(locale: Locale, zh: string, en: string) {
  return locale === 'zh-CN' ? zh : en
}

function parseSettings(items: SettingItem[] | undefined) {
  const mapping = new Map((items ?? []).map((item) => [item.key, item.value]))
  return {
    gatewayKeys: splitGatewayKeys(mapping.get(GATEWAY_API_KEYS) ?? ''),
    draft: {
      proxyUrl: mapping.get(PROXY_URL) ?? '',
      statsSaveInterval: mapping.get(STATS_SAVE_INTERVAL) ?? '60',
      corsAllowOrigins: mapping.get(CORS_ALLOW_ORIGINS) ?? '*',
      relayLogKeepEnabled: !['0', 'false', 'no', 'off'].includes((mapping.get(RELAY_LOG_KEEP_ENABLED) ?? 'true').toLowerCase()),
      relayLogKeepPeriod: mapping.get(RELAY_LOG_KEEP_PERIOD) ?? '7',
      circuitBreakerThreshold: mapping.get(CIRCUIT_BREAKER_THRESHOLD) ?? '3',
      circuitBreakerCooldown: mapping.get(CIRCUIT_BREAKER_COOLDOWN) ?? '60',
      circuitBreakerMaxCooldown: mapping.get(CIRCUIT_BREAKER_MAX_COOLDOWN) ?? '600',
      siteName: mapping.get(SITE_NAME) ?? 'Lens',
      siteLogoUrl: mapping.get(SITE_LOGO_URL) ?? '',
    } satisfies DraftState,
  }
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

function normalizeOriginList(rawValue: string) {
  const items: string[] = []
  const seen = new Set<string>()
  for (const chunk of rawValue.replace(/\r/g, '\n').replaceAll('，', ',').split('\n')) {
    for (const part of chunk.split(',')) {
      const normalized = part.trim()
      if (!normalized || seen.has(normalized)) {
        continue
      }
      seen.add(normalized)
      items.push(normalized)
    }
  }
  if (items.includes('*')) {
    return '*'
  }
  return items.join(',')
}

function maskGatewayKey(value: string) {
  if (value.length <= 12) {
    return value[0] + '*'.repeat(Math.max(value.length - 2, 1)) + value.slice(-1)
  }
  return value.slice(0, 4) + '*'.repeat(Math.max(value.length - 8, 4)) + value.slice(-4)
}

function generateGatewayKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return 'sk-lens-' + crypto.randomUUID().replaceAll('-', '')
  }
  return 'sk-lens-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

function saveButtonLabel(locale: Locale, saving: boolean) {
  if (saving) {
    return titleForLocale(locale, '保存中...', 'Saving...')
  }
  return titleForLocale(locale, '保存设置', 'Save settings')
}

function formatLastSynced(value: string | null | undefined, locale: Locale) {
  if (!value) {
    return titleForLocale(locale, '未同步', 'Never synced')
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return titleForLocale(locale, '未同步', 'Never synced')
  }
  return date.toLocaleString(locale)
}

function SettingCard({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  children: React.ReactNode
}) {
  return (
    <section className={cardClassName()}>
      <div className="flex items-center gap-2 text-base font-semibold text-[var(--text)]">
        <Icon className="h-4 w-4 text-[var(--muted)]" />
        <h2>{title}</h2>
      </div>
      <div className="mt-5 space-y-4">{children}</div>
    </section>
  )
}

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-medium text-[var(--muted)]">{label}</span>
      {children}
    </label>
  )
}

function ReadonlyRow({
  label,
  value,
}: {
  label: string
  value: React.ReactNode
}) {
  return (
    <div className="grid gap-1 rounded-2xl bg-[var(--panel)] px-4 py-3 sm:grid-cols-[120px_minmax(0,1fr)] sm:items-center sm:gap-3">
      <span className="text-sm text-[var(--muted)]">{label}</span>
      <span className="min-w-0 text-sm font-medium text-[var(--text)] sm:text-left">{value}</span>
    </div>
  )
}

function SettingsColumn({ children }: { children: React.ReactNode }) {
  return <div className="space-y-4">{children}</div>
}

export function SettingsScreen() {
  const queryClient = useQueryClient()
  const { locale, setLocale } = useI18n()
  const toast = useToast()
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => apiRequest<SettingItem[]>('/settings') })
  const { data: profile } = useQuery({ queryKey: ['auth-me'], queryFn: () => apiRequest<AdminProfile>('/auth/me') })
  const { data: appInfo } = useQuery({ queryKey: ['app-info'], queryFn: () => apiRequest<AppInfo>('/app-info') })
  const { data: modelPrices } = useQuery({ queryKey: ['model-prices'], queryFn: () => apiRequest<ModelPriceListResponse>('/model-prices') })

  const [draft, setDraft] = useState<DraftState>(EMPTY_DRAFT)
  const [gatewayKeys, setGatewayKeys] = useState<string[]>([])
  const [newGatewayKey, setNewGatewayKey] = useState('')
  const [passwordForm, setPasswordForm] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' })
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [saving, setSaving] = useState(false)
  const [clearingLogs, setClearingLogs] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)
  const [accountDialogOpen, setAccountDialogOpen] = useState(false)
  const [copiedKey, setCopiedKey] = useState('')
  const [syncingPrices, setSyncingPrices] = useState(false)

  useEffect(() => {
    const parsed = parseSettings(settings)
    setDraft(parsed.draft)
    setGatewayKeys(parsed.gatewayKeys)
  }, [settings])

  function setDraftValue<K extends keyof DraftState>(key: K, value: DraftState[K]) {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  function appendGatewayKey() {
    const normalized = newGatewayKey.trim()
    if (!normalized) {
      return
    }
    setGatewayKeys((current) => current.includes(normalized) ? current : [...current, normalized])
    setNewGatewayKey('')
    toast.success(titleForLocale(locale, 'API Key 已创建', 'API key created'))
  }

  function removeGatewayKey(value: string) {
    setGatewayKeys((current) => current.filter((item) => item !== value))
    toast.success(titleForLocale(locale, 'API Key 已删除', 'API key deleted'))
  }

  async function copyGatewayKey(value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setCopiedKey(value)
      toast.success(titleForLocale(locale, 'API Key 已复制', 'API key copied'))
      setTimeout(() => {
        setCopiedKey((current) => current === value ? '' : current)
      }, 1500)
    } catch {
      const message = titleForLocale(locale, '复制失败', 'Failed to copy')
      setError(message)
      toast.error(message)
    }
  }

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['settings'] }),
      queryClient.invalidateQueries({ queryKey: ['app-info'] }),
      queryClient.invalidateQueries({ queryKey: ['model-prices'] }),
      queryClient.invalidateQueries({ queryKey: ['public-branding'] }),
    ])
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setSaved('')
    try {
      const items: FieldSpec[] = [
        { key: GATEWAY_API_KEYS, value: gatewayKeys.join('\n') },
        { key: GATEWAY_API_KEY_HINT, value: '' },
        { key: PROXY_URL, value: draft.proxyUrl.trim() },
        { key: STATS_SAVE_INTERVAL, value: draft.statsSaveInterval.trim() || '60' },
        { key: CORS_ALLOW_ORIGINS, value: normalizeOriginList(draft.corsAllowOrigins) || '*' },
        { key: RELAY_LOG_KEEP_ENABLED, value: draft.relayLogKeepEnabled ? 'true' : 'false' },
        { key: RELAY_LOG_KEEP_PERIOD, value: draft.relayLogKeepPeriod.trim() || '7' },
        { key: CIRCUIT_BREAKER_THRESHOLD, value: draft.circuitBreakerThreshold.trim() || '3' },
        { key: CIRCUIT_BREAKER_COOLDOWN, value: draft.circuitBreakerCooldown.trim() || '60' },
        { key: CIRCUIT_BREAKER_MAX_COOLDOWN, value: draft.circuitBreakerMaxCooldown.trim() || '600' },
        { key: SITE_NAME, value: draft.siteName.trim() || 'Lens' },
        { key: SITE_LOGO_URL, value: draft.siteLogoUrl.trim() },
      ]
      await apiRequest<SettingItem[]>('/settings', { method: 'PUT', body: JSON.stringify({ items }) })
      const message = titleForLocale(locale, '设置已保存', 'Settings saved')
      setSaved(message)
      toast.success(message)
      await refresh()
    } catch (requestError) {
      const message = requestError instanceof ApiError ? requestError.message : titleForLocale(locale, '保存设置失败', 'Failed to save settings')
      setError(message)
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function clearLogs() {
    const confirmed = window.confirm(titleForLocale(locale, '确认删除全部请求日志？', 'Delete all request logs?'))
    if (!confirmed) {
      return
    }
    setClearingLogs(true)
    setError('')
    setSaved('')
    try {
      await apiRequest<void>('/request-logs', { method: 'DELETE' })
      const message = titleForLocale(locale, '请求日志已清空', 'Request logs cleared')
      setSaved(message)
      toast.success(message)
      await queryClient.invalidateQueries({ queryKey: ['request-logs'] })
    } catch (requestError) {
      const message = requestError instanceof ApiError ? requestError.message : titleForLocale(locale, '清空请求日志失败', 'Failed to clear request logs')
      setError(message)
      toast.error(message)
    } finally {
      setClearingLogs(false)
    }
  }

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSaved('')
    if (!passwordForm.currentPassword || !passwordForm.newPassword) {
      const message = titleForLocale(locale, '请填写完整密码', 'Please fill in both passwords')
      setError(message)
      toast.error(message)
      return
    }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      const message = titleForLocale(locale, '两次新密码不一致', 'The new passwords do not match')
      setError(message)
      toast.error(message)
      return
    }
    const payload: AdminPasswordChangePayload = {
      current_password: passwordForm.currentPassword,
      new_password: passwordForm.newPassword,
    }
    setChangingPassword(true)
    try {
      await apiRequest<void>('/auth/password', { method: 'PUT', body: JSON.stringify(payload) })
      const message = titleForLocale(locale, '密码已更新', 'Password updated')
      setSaved(message)
      toast.success(message)
      setPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' })
      setAccountDialogOpen(false)
    } catch (requestError) {
      const message = requestError instanceof ApiError ? requestError.message : titleForLocale(locale, '修改密码失败', 'Failed to update password')
      setError(message)
      toast.error(message)
    } finally {
      setChangingPassword(false)
    }
  }

  async function syncPrices() {
    setSyncingPrices(true)
    setError('')
    setSaved('')
    try {
      await apiRequest<ModelPriceListResponse>('/model-prices/sync', { method: 'POST' })
      const message = titleForLocale(locale, '模型价格已同步', 'Model prices synced')
      setSaved(message)
      toast.success(message)
      await queryClient.invalidateQueries({ queryKey: ['model-prices'] })
    } catch (requestError) {
      const message = requestError instanceof ApiError ? requestError.message : titleForLocale(locale, '同步模型价格失败', 'Failed to sync model prices')
      setError(message)
      toast.error(message)
    } finally {
      setSyncingPrices(false)
    }
  }

  function renderInfoCard() {
    return (
      <SettingCard icon={Info} title={titleForLocale(locale, '版本信息', 'Version')}>
        <ReadonlyRow label={titleForLocale(locale, '版本', 'Version')} value={appInfo?.frontend_version || appInfo?.backend_version || '-'} />
        <ReadonlyRow label={titleForLocale(locale, '环境', 'Environment')} value={appInfo?.app_env || '-'} />
      </SettingCard>
    )
  }

  function renderAppearanceCard() {
    return (
      <SettingCard icon={Palette} title={titleForLocale(locale, '外观', 'Appearance')}>
        <Field label={titleForLocale(locale, '语言', 'Language')}>
          <div className="inline-flex gap-2">
            <button type="button" onClick={() => setLocale('zh-CN')} className={locale === 'zh-CN' ? 'rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white' : 'rounded-lg px-3 py-1.5 text-xs text-[var(--muted)] hover:bg-[var(--panel-soft)]'}>简体中文</button>
            <button type="button" onClick={() => setLocale('en-US')} className={locale === 'en-US' ? 'rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white' : 'rounded-lg px-3 py-1.5 text-xs text-[var(--muted)] hover:bg-[var(--panel-soft)]'}>English</button>
          </div>
        </Field>
        <Field label={titleForLocale(locale, '站点名称', 'Site name')}>
          <input className={inputClassName()} value={draft.siteName} onChange={(event) => setDraftValue('siteName', event.target.value)} placeholder="Lens" />
        </Field>
        <Field label={titleForLocale(locale, 'Logo 地址', 'Logo URL')}>
          <input className={inputClassName()} value={draft.siteLogoUrl} onChange={(event) => setDraftValue('siteLogoUrl', event.target.value)} placeholder="https://example.com/logo.svg" />
        </Field>
        <div className="flex items-center gap-3 rounded-2xl bg-[var(--panel)] px-4 py-3">
          <span className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--panel-strong)]">
            {draft.siteLogoUrl.trim() ? <Image src={draft.siteLogoUrl.trim()} alt={draft.siteName || 'logo'} width={48} height={48} className="h-12 w-12 object-cover" unoptimized /> : <ImageIcon size={18} className="text-[var(--muted)]" />}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-[var(--text)]">{draft.siteName.trim() || 'Lens'}</div>
            <div className="truncate text-xs text-[var(--muted)]">{draft.siteLogoUrl.trim() || titleForLocale(locale, '未设置 Logo', 'No logo configured')}</div>
          </div>
        </div>
      </SettingCard>
    )
  }

  function renderAccountCard() {
    return (
      <SettingCard icon={UserRound} title={titleForLocale(locale, '账号', 'Account')}>
        <ReadonlyRow label={titleForLocale(locale, '用户名', 'Username')} value={profile?.username || 'admin'} />
        <button type="button" className="inline-flex h-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 text-sm text-[var(--text)] transition-colors hover:bg-[var(--panel-soft)]" onClick={() => setAccountDialogOpen(true)}>{titleForLocale(locale, '修改密码', 'Change password')}</button>
      </SettingCard>
    )
  }

  function renderSystemCard() {
    return (
      <SettingCard icon={ServerCog} title={titleForLocale(locale, '系统', 'System')}>
        <Field label={titleForLocale(locale, '全局代理地址', 'Global proxy URL')}>
          <input className={inputClassName()} value={draft.proxyUrl} onChange={(event) => setDraftValue('proxyUrl', event.target.value)} placeholder="http://127.0.0.1:7890" />
        </Field>
        <Field label={titleForLocale(locale, '统计保存周期', 'Stats save interval')}>
          <input className={inputClassName()} type="number" min="1" value={draft.statsSaveInterval} onChange={(event) => setDraftValue('statsSaveInterval', event.target.value)} />
        </Field>
        <Field label={titleForLocale(locale, 'CORS 跨域名单', 'CORS allow origins')}>
          <textarea className={textareaClassName()} value={draft.corsAllowOrigins} onChange={(event) => setDraftValue('corsAllowOrigins', event.target.value)} placeholder={"*\nhttp://localhost:3000"} />
        </Field>
      </SettingCard>
    )
  }

  function renderLogCard() {
    return (
      <SettingCard icon={CircleAlert} title={titleForLocale(locale, '日志', 'Logs')}>
        <Field label={titleForLocale(locale, '保留日志', 'Keep logs')}>
          <div className="inline-flex gap-2">
            <button type="button" onClick={() => setDraftValue('relayLogKeepEnabled', true)} className={draft.relayLogKeepEnabled ? 'rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white' : 'rounded-lg px-3 py-1.5 text-xs text-[var(--muted)] hover:bg-[var(--panel-soft)]'}>{titleForLocale(locale, '开启', 'On')}</button>
            <button type="button" onClick={() => setDraftValue('relayLogKeepEnabled', false)} className={!draft.relayLogKeepEnabled ? 'rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white' : 'rounded-lg px-3 py-1.5 text-xs text-[var(--muted)] hover:bg-[var(--panel-soft)]'}>{titleForLocale(locale, '关闭', 'Off')}</button>
          </div>
        </Field>
        <Field label={titleForLocale(locale, '保留天数', 'Keep days')}>
          <input className={inputClassName()} type="number" min="1" value={draft.relayLogKeepPeriod} onChange={(event) => setDraftValue('relayLogKeepPeriod', event.target.value)} disabled={!draft.relayLogKeepEnabled} />
        </Field>
        <button type="button" className="inline-flex h-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 text-sm text-[var(--danger)] transition-colors hover:bg-[var(--panel-soft)] disabled:opacity-60" onClick={() => void clearLogs()} disabled={clearingLogs}><Trash2 size={15} className="mr-2" />{clearingLogs ? titleForLocale(locale, '清空中...', 'Clearing...') : titleForLocale(locale, '清空请求日志', 'Clear request logs')}</button>
      </SettingCard>
    )
  }

  function renderApiKeyCard() {
    return (
      <SettingCard icon={ShieldCheck} title={titleForLocale(locale, 'API 密钥', 'API keys')}>
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <input className={inputClassName()} value={newGatewayKey} onChange={(event) => setNewGatewayKey(event.target.value)} placeholder={titleForLocale(locale, '输入或生成新的 API Key', 'Enter or generate a new API key')} />
          <button type="button" className="inline-flex h-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 text-sm text-[var(--text)] transition-colors hover:bg-[var(--panel-soft)]" onClick={() => setNewGatewayKey(generateGatewayKey())}>{titleForLocale(locale, '生成', 'Generate')}</button>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="inline-flex h-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 text-sm text-[var(--text)] transition-colors hover:bg-[var(--panel-soft)]" onClick={appendGatewayKey}>{titleForLocale(locale, '加入列表', 'Add key')}</button>
        </div>
        <div className="grid gap-2">
          {gatewayKeys.length ? gatewayKeys.map((item) => (
            <div key={item} className="flex items-center justify-between gap-3 rounded-2xl bg-[var(--panel)] px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-[var(--text)]">{maskGatewayKey(item)}</div>
              </div>
              <div className="flex items-center gap-1">
                <button type="button" className="inline-flex h-8 w-8 items-center justify-center rounded-xl text-[var(--muted)] transition-colors hover:bg-[var(--panel-soft)] hover:text-[var(--text)]" onClick={() => void copyGatewayKey(item)} title={titleForLocale(locale, '复制', 'Copy')}>
                  {copiedKey === item ? <Check size={14} className="text-[var(--success)]" /> : <Copy size={14} />}
                </button>
                <button type="button" className="inline-flex h-8 w-8 items-center justify-center rounded-xl text-[var(--muted)] transition-colors hover:bg-[var(--panel-soft)] hover:text-[var(--danger)]" onClick={() => removeGatewayKey(item)} title={titleForLocale(locale, '删除', 'Delete')}>
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          )) : (
            <div className="rounded-2xl border border-dashed border-[var(--line)] bg-[var(--panel)] px-4 py-8 text-center text-sm text-[var(--muted)]">{titleForLocale(locale, '当前没有 API 密钥', 'No API keys')}</div>
          )}
        </div>
      </SettingCard>
    )
  }

  function renderCircuitCard() {
    return (
      <SettingCard icon={ShieldCheck} title={titleForLocale(locale, '熔断器', 'Circuit breaker')}>
        <Field label={titleForLocale(locale, '失败阈值', 'Failure threshold')}>
          <input className={inputClassName()} type="number" min="0" value={draft.circuitBreakerThreshold} onChange={(event) => setDraftValue('circuitBreakerThreshold', event.target.value)} />
        </Field>
        <Field label={titleForLocale(locale, '基础冷却秒数', 'Cooldown seconds')}>
          <input className={inputClassName()} type="number" min="0" value={draft.circuitBreakerCooldown} onChange={(event) => setDraftValue('circuitBreakerCooldown', event.target.value)} />
        </Field>
        <Field label={titleForLocale(locale, '最大冷却秒数', 'Max cooldown seconds')}>
          <input className={inputClassName()} type="number" min="0" value={draft.circuitBreakerMaxCooldown} onChange={(event) => setDraftValue('circuitBreakerMaxCooldown', event.target.value)} />
        </Field>
      </SettingCard>
    )
  }

  function renderPriceCard() {
    return (
      <SettingCard icon={KeyRound} title={titleForLocale(locale, '模型价格', 'Model prices')}>
        <ReadonlyRow label={titleForLocale(locale, '最近同步', 'Last sync')} value={formatLastSynced(modelPrices?.last_synced_at, locale)} />
        <button type="button" className="inline-flex h-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 text-sm text-[var(--text)] transition-colors hover:bg-[var(--panel-soft)] disabled:opacity-60" onClick={() => void syncPrices()} disabled={syncingPrices}>{syncingPrices ? titleForLocale(locale, '同步中...', 'Syncing...') : titleForLocale(locale, '同步价格', 'Sync prices')}</button>
      </SettingCard>
    )
  }

  return (
    <section className="space-y-4">
      <form className="space-y-6" onSubmit={(e) => void submit(e)}>
        {typeof document !== 'undefined' && document.getElementById('header-portal') ? createPortal(
          <div className="flex flex-1 items-center justify-end gap-2">
            <button className="inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--line)] bg-[var(--panel-strong)] px-3.5 text-[13px] font-medium text-[var(--muted)] shadow-sm transition-all hover:bg-[var(--panel-soft)] hover:text-[var(--text)]" type="button" onClick={() => void refresh()}>
              <RotateCcw size={15} />
              <span className="hidden sm:inline">{titleForLocale(locale, '刷新', 'Refresh')}</span>
            </button>
            <button className="inline-flex h-9 items-center gap-2 rounded-lg bg-[var(--accent)] px-3.5 text-[13px] font-medium text-white shadow-sm transition-colors hover:opacity-90 disabled:opacity-60" type="submit" disabled={saving}>
              <Save size={15} />
              {saveButtonLabel(locale, saving)}
            </button>
          </div>,
          document.getElementById('header-portal')!
        ) : null}

        <div className="space-y-4 md:hidden mt-2">
          {renderInfoCard()}
          {renderAccountCard()}
          {renderLogCard()}
          {renderAppearanceCard()}
          {renderApiKeyCard()}
          {renderSystemCard()}
          {renderCircuitCard()}
        </div>

        <div className="hidden gap-4 md:grid md:grid-cols-2 md:items-start">
          <SettingsColumn>
            {renderInfoCard()}
            {renderAccountCard()}
            {renderAppearanceCard()}
            {renderSystemCard()}
          </SettingsColumn>
          <SettingsColumn>
            {renderLogCard()}
            {renderApiKeyCard()}
            {renderCircuitCard()}
          </SettingsColumn>
        </div>

        {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
        {saved ? <p className="text-sm text-[var(--success)]">{saved}</p> : null}
      </form>

      <Dialog.Root open={accountDialogOpen} onOpenChange={setAccountDialogOpen}>
        <AppDialogContent className="max-w-lg" title={titleForLocale(locale, '修改密码', 'Change password')}>
          <form className="grid gap-4" onSubmit={submitPassword}>
            <Field label={titleForLocale(locale, '当前密码', 'Current password')}>
              <input className={inputClassName()} type="password" value={passwordForm.currentPassword} onChange={(event) => setPasswordForm((current) => ({ ...current, currentPassword: event.target.value }))} autoComplete="current-password" />
            </Field>
            <Field label={titleForLocale(locale, '新密码', 'New password')}>
              <input className={inputClassName()} type="password" value={passwordForm.newPassword} onChange={(event) => setPasswordForm((current) => ({ ...current, newPassword: event.target.value }))} autoComplete="new-password" />
            </Field>
            <Field label={titleForLocale(locale, '确认新密码', 'Confirm new password')}>
              <input className={inputClassName()} type="password" value={passwordForm.confirmPassword} onChange={(event) => setPasswordForm((current) => ({ ...current, confirmPassword: event.target.value }))} autoComplete="new-password" />
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="inline-flex h-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 text-sm text-[var(--text)]" onClick={() => setAccountDialogOpen(false)}>{titleForLocale(locale, '取消', 'Cancel')}</button>
              <button type="submit" className="inline-flex h-10 items-center justify-center rounded-xl bg-[var(--accent)] px-4 text-sm font-medium text-white disabled:opacity-60" disabled={changingPassword}>{changingPassword ? titleForLocale(locale, '提交中...', 'Updating...') : titleForLocale(locale, '确认修改', 'Update password')}</button>
            </div>
          </form>
        </AppDialogContent>
      </Dialog.Root>
    </section>
  )
}
