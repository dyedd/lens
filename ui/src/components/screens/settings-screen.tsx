"use client"

import Image from "next/image"
import { useEffect, useState, type ComponentType, type FormEvent, type ReactNode } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  ImageIcon,
  Palette,
  RotateCcw,
  Save,
  ServerCog,
  ShieldAlert,
  TestTubeDiagonal,
  UserRound,
  TimerReset,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Textarea } from "@/components/ui/textarea"
import {
  ApiError,
  type AdminProfile,
  type AdminProfileUpdatePayload,
  type AdminProfileUpdateResponse,
  type SettingItem,
  apiRequest,
} from "@/lib/api"
import { setStoredToken } from "@/lib/auth"
import { useI18n, type Locale } from "@/lib/i18n"
import { DEFAULT_MODEL_TEST_PROMPTS, MODEL_TEST_PROMPTS_SETTING_KEY, parseModelTestPrompts, serializeModelTestPrompts } from "@/lib/model-test-prompts"
import { cn } from "@/lib/utils"

const PROXY_URL = "proxy_url"
const CORS_ALLOW_ORIGINS = "cors_allow_origins"
const CIRCUIT_BREAKER_THRESHOLD = "circuit_breaker_threshold"
const CIRCUIT_BREAKER_COOLDOWN = "circuit_breaker_cooldown"
const CIRCUIT_BREAKER_MAX_COOLDOWN = "circuit_breaker_max_cooldown"
const HEALTH_WINDOW_SECONDS = "health_window_seconds"
const HEALTH_PENALTY_WEIGHT = "health_penalty_weight"
const HEALTH_MIN_SAMPLES = "health_min_samples"
const SITE_NAME = "site_name"
const SITE_LOGO_URL = "site_logo_url"
const TIME_ZONE = "time_zone"

const TIME_ZONE_OPTIONS = [
  { value: "Asia/Shanghai", label: "Asia/Shanghai" },
  { value: "UTC", label: "UTC" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "America/New_York", label: "America/New_York" },
] as const

type DraftState = {
  proxyUrl: string
  corsAllowOrigins: string
  circuitBreakerThreshold: string
  circuitBreakerCooldown: string
  circuitBreakerMaxCooldown: string
  healthWindowSeconds: string
  healthPenaltyWeight: string
  healthMinSamples: string
  siteName: string
  siteLogoUrl: string
  timeZone: string
  modelTestPrompts: string
}

const EMPTY_DRAFT: DraftState = {
  proxyUrl: "",
  corsAllowOrigins: "*",
  circuitBreakerThreshold: "3",
  circuitBreakerCooldown: "60",
  circuitBreakerMaxCooldown: "600",
  healthWindowSeconds: "300",
  healthPenaltyWeight: "0.5",
  healthMinSamples: "10",
  siteName: "Lens",
  siteLogoUrl: "",
  timeZone: "Asia/Shanghai",
  modelTestPrompts: DEFAULT_MODEL_TEST_PROMPTS.join("\n"),
}

function titleForLocale(locale: Locale, zh: string, en: string) {
  return locale === "zh-CN" ? zh : en
}

function parseSettings(items: SettingItem[] | undefined) {
  const mapping = new Map((items ?? []).map((item) => [item.key, item.value]))
  return {
    proxyUrl: mapping.get(PROXY_URL) ?? "",
    corsAllowOrigins: mapping.get(CORS_ALLOW_ORIGINS) ?? "*",
    circuitBreakerThreshold: mapping.get(CIRCUIT_BREAKER_THRESHOLD) ?? "3",
    circuitBreakerCooldown: mapping.get(CIRCUIT_BREAKER_COOLDOWN) ?? "60",
    circuitBreakerMaxCooldown: mapping.get(CIRCUIT_BREAKER_MAX_COOLDOWN) ?? "600",
    healthWindowSeconds: mapping.get(HEALTH_WINDOW_SECONDS) ?? "300",
    healthPenaltyWeight: mapping.get(HEALTH_PENALTY_WEIGHT) ?? "0.5",
    healthMinSamples: mapping.get(HEALTH_MIN_SAMPLES) ?? "10",
    siteName: mapping.get(SITE_NAME) ?? "Lens",
    siteLogoUrl: mapping.get(SITE_LOGO_URL) ?? "",
    timeZone: mapping.get(TIME_ZONE) ?? "Asia/Shanghai",
    modelTestPrompts: parseModelTestPrompts(mapping.get(MODEL_TEST_PROMPTS_SETTING_KEY)).join("\n"),
  } satisfies DraftState
}

function normalizeOriginList(rawValue: string) {
  const items: string[] = []
  const seen = new Set<string>()
  for (const chunk of rawValue.replace(/\r/g, "\n").replaceAll("，", ",").split("\n")) {
    for (const part of chunk.split(",")) {
      const normalized = part.trim()
      if (!normalized || seen.has(normalized)) {
        continue
      }
      seen.add(normalized)
      items.push(normalized)
    }
  }
  if (items.includes("*")) {
    return "*"
  }
  return items.join(",")
}

function saveButtonLabel(locale: Locale, saving: boolean) {
  if (saving) {
    return titleForLocale(locale, "保存中...", "Saving...")
  }
  return titleForLocale(locale, "保存设置", "Save settings")
}

function SettingCard({
  icon: Icon,
  title,
  className,
  children,
}: {
  icon: ComponentType<{ className?: string }>
  title: string
  className?: string
  children: ReactNode
}) {
  return (
    <Card className={cn("py-0", className)}>
      <CardHeader className="px-4 pt-4 pb-0 sm:px-5 sm:pt-5">
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Icon className="size-4 text-muted-foreground" />
          <span>{title}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 px-4 py-4 sm:px-5 sm:py-5">{children}</CardContent>
    </Card>
  )
}

export function SettingsScreen() {
  const queryClient = useQueryClient()
  const { locale, setLocale } = useI18n()
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 5 * 60_000,
  })
  const { data: profile } = useQuery({
    queryKey: ["auth-me"],
    queryFn: () => apiRequest<AdminProfile>("/admin/session"),
    staleTime: 5 * 60_000,
  })

  const [draft, setDraft] = useState<DraftState>(EMPTY_DRAFT)
  const [accountForm, setAccountForm] = useState({
    username: "admin",
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  })
  const [saving, setSaving] = useState(false)
  const [updatingAccount, setUpdatingAccount] = useState(false)

  useEffect(() => {
    setDraft(parseSettings(settings))
  }, [settings])

  useEffect(() => {
    setAccountForm((current) => ({
      ...current,
      username: profile?.username || "admin",
    }))
  }, [profile?.username])

  function setDraftValue<K extends keyof DraftState>(key: K, value: DraftState[K]) {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["settings"] }),
      queryClient.invalidateQueries({ queryKey: ["public-branding"] }),
      queryClient.invalidateQueries({ queryKey: ["app-info"] }),
      queryClient.invalidateQueries({ queryKey: ["model-groups"] }),
      queryClient.invalidateQueries({ queryKey: ["overview-dashboard"] }),
      queryClient.invalidateQueries({ queryKey: ["overview-metrics"] }),
      queryClient.invalidateQueries({ queryKey: ["overview-models"] }),
    ])
  }

  async function submitSettings() {
    setSaving(true)
    try {
      const items: SettingItem[] = [
        { key: PROXY_URL, value: draft.proxyUrl.trim() },
        { key: CORS_ALLOW_ORIGINS, value: normalizeOriginList(draft.corsAllowOrigins) || "*" },
        { key: CIRCUIT_BREAKER_THRESHOLD, value: draft.circuitBreakerThreshold.trim() || "3" },
        { key: CIRCUIT_BREAKER_COOLDOWN, value: draft.circuitBreakerCooldown.trim() || "60" },
        { key: CIRCUIT_BREAKER_MAX_COOLDOWN, value: draft.circuitBreakerMaxCooldown.trim() || "600" },
        { key: HEALTH_WINDOW_SECONDS, value: draft.healthWindowSeconds.trim() || "300" },
        { key: HEALTH_PENALTY_WEIGHT, value: draft.healthPenaltyWeight.trim() || "0.5" },
        { key: HEALTH_MIN_SAMPLES, value: draft.healthMinSamples.trim() || "10" },
        { key: SITE_NAME, value: draft.siteName.trim() || "Lens" },
        { key: SITE_LOGO_URL, value: draft.siteLogoUrl.trim() },
        { key: TIME_ZONE, value: draft.timeZone.trim() || "Asia/Shanghai" },
        { key: MODEL_TEST_PROMPTS_SETTING_KEY, value: serializeModelTestPrompts(draft.modelTestPrompts) },
      ]
      await apiRequest<SettingItem[]>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ items }),
      })
      toast.success(titleForLocale(locale, "设置已保存", "Settings saved"))
      await refresh()
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(locale, "保存设置失败", "Failed to save settings")
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  async function submitAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const nextUsername = accountForm.username.trim()
    const wantsPasswordUpdate = Boolean(
      accountForm.currentPassword || accountForm.newPassword || accountForm.confirmPassword
    )
    const usernameChanged = nextUsername !== (profile?.username || "admin")

    if (!nextUsername) {
      toast.error(titleForLocale(locale, "用户名不能为空", "Username is required"))
      return
    }

    if (!usernameChanged && !wantsPasswordUpdate) {
      toast.success(titleForLocale(locale, "没有需要保存的账号变更", "No account changes to save"))
      return
    }

    if (wantsPasswordUpdate && (!accountForm.currentPassword || !accountForm.newPassword)) {
      toast.error(titleForLocale(locale, "请填写完整密码", "Please fill in both passwords"))
      return
    }

    if (accountForm.newPassword !== accountForm.confirmPassword) {
      toast.error(titleForLocale(locale, "两次新密码不一致", "The new passwords do not match"))
      return
    }

    const payload: AdminProfileUpdatePayload = {
      username: nextUsername,
      current_password: accountForm.currentPassword,
      new_password: accountForm.newPassword,
    }
    setUpdatingAccount(true)
    try {
      const response = await apiRequest<AdminProfileUpdateResponse>("/admin/profile", {
        method: "PUT",
        body: JSON.stringify(payload),
      })
      setStoredToken(response.access_token)
      window.sessionStorage.removeItem("lens_admin_profile_cache")
      queryClient.setQueryData(["auth-me"], response.profile)
      await queryClient.invalidateQueries({ queryKey: ["auth-me"] })
      toast.success(titleForLocale(locale, "账号已更新", "Account updated"))
      setAccountForm({
        username: response.profile.username,
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
      })
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(locale, "更新账号失败", "Failed to update account")
      toast.error(message)
    } finally {
      setUpdatingAccount(false)
    }
  }

  function renderAppearanceCard() {
    return (
      <SettingCard icon={Palette} title={titleForLocale(locale, "站点外观", "Appearance")}>
        <FieldGroup>
          <Field>
            <FieldLabel>{titleForLocale(locale, "语言", "Language")}</FieldLabel>
            <SegmentedControl
              className="!w-fit self-start"
              value={locale}
              onValueChange={(value) => setLocale(value)}
              options={[
                { value: "zh-CN", label: "简体中文" },
                { value: "en-US", label: "English" },
              ]}
            />
          </Field>
          <Field>
            <FieldLabel>{titleForLocale(locale, "站点名称", "Site name")}</FieldLabel>
            <Input value={draft.siteName} onChange={(event) => setDraftValue("siteName", event.target.value)} placeholder="Lens" />
          </Field>
          <Field>
            <FieldLabel>{titleForLocale(locale, "Logo 地址", "Logo URL")}</FieldLabel>
            <Input
              value={draft.siteLogoUrl}
              onChange={(event) => setDraftValue("siteLogoUrl", event.target.value)}
              placeholder="https://example.com/logo.svg"
            />
          </Field>
        </FieldGroup>
        <div className="flex items-center gap-3 rounded-md border bg-muted/40 px-4 py-3">
          <span className="flex size-12 items-center justify-center overflow-hidden rounded-md border bg-background">
            {draft.siteLogoUrl.trim() ? (
              <Image
                src={draft.siteLogoUrl.trim()}
                alt={draft.siteName || "logo"}
                width={48}
                height={48}
                className="size-12 object-cover"
                unoptimized
              />
            ) : (
              <ImageIcon className="text-muted-foreground" />
            )}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-foreground">{draft.siteName.trim() || "Lens"}</div>
            <div className="truncate text-xs text-muted-foreground">
              {draft.siteLogoUrl.trim() || titleForLocale(locale, "未设置 Logo", "No logo configured")}
            </div>
          </div>
        </div>
      </SettingCard>
    )
  }

  function renderTimeCard() {
    return (
      <SettingCard icon={TimerReset} title={titleForLocale(locale, "时间", "Time")}>
        <FieldGroup>
          <Field>
            <FieldLabel>{titleForLocale(locale, "时区", "Time zone")}</FieldLabel>
            <NativeSelect
              className="w-full"
              value={draft.timeZone || "Asia/Shanghai"}
              onChange={(event) => setDraftValue("timeZone", event.target.value)}
            >
              {TIME_ZONE_OPTIONS.map((option) => (
                <NativeSelectOption key={option.value} value={option.value}>
                  {option.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </Field>
        </FieldGroup>
      </SettingCard>
    )
  }

  function renderAccountCard() {
    return (
      <SettingCard icon={UserRound} title={titleForLocale(locale, "账号", "Account")}>
        <form className="flex flex-col gap-4" onSubmit={submitAccount}>
          <FieldGroup>
            <Field>
              <FieldLabel>{titleForLocale(locale, "用户名", "Username")}</FieldLabel>
              <Input
                value={accountForm.username}
                onChange={(event) => setAccountForm((current) => ({ ...current, username: event.target.value }))}
                autoComplete="username"
              />
            </Field>
            <Field>
              <FieldLabel>{titleForLocale(locale, "当前密码", "Current password")}</FieldLabel>
              <Input
                type="password"
                value={accountForm.currentPassword}
                onChange={(event) => setAccountForm((current) => ({ ...current, currentPassword: event.target.value }))}
                autoComplete="current-password"
              />
            </Field>
            <Field>
              <FieldLabel>{titleForLocale(locale, "新密码", "New password")}</FieldLabel>
              <Input
                type="password"
                value={accountForm.newPassword}
                onChange={(event) => setAccountForm((current) => ({ ...current, newPassword: event.target.value }))}
                autoComplete="new-password"
              />
            </Field>
            <Field>
              <FieldLabel>{titleForLocale(locale, "确认新密码", "Confirm new password")}</FieldLabel>
              <Input
                type="password"
                value={accountForm.confirmPassword}
                onChange={(event) => setAccountForm((current) => ({ ...current, confirmPassword: event.target.value }))}
                autoComplete="new-password"
              />
            </Field>
          </FieldGroup>
          <Button type="submit" variant="outline" disabled={updatingAccount}>
            {updatingAccount ? titleForLocale(locale, "提交中...", "Updating...") : titleForLocale(locale, "保存账号", "Save account")}
          </Button>
        </form>
      </SettingCard>
    )
  }

  function renderSystemCard() {
    return (
      <SettingCard icon={ServerCog} title={titleForLocale(locale, "网关", "Gateway")}>
        <FieldGroup>
          <Field>
            <FieldLabel>{titleForLocale(locale, "全局代理地址", "Global proxy URL")}</FieldLabel>
            <Input value={draft.proxyUrl} onChange={(event) => setDraftValue("proxyUrl", event.target.value)} placeholder="http://127.0.0.1:7890" />
          </Field>
          <Field>
            <FieldLabel>{titleForLocale(locale, "CORS 跨域名单", "CORS allow origins")}</FieldLabel>
            <Textarea
              className="min-h-[92px]"
              value={draft.corsAllowOrigins}
              onChange={(event) => setDraftValue("corsAllowOrigins", event.target.value)}
              placeholder={"*\nhttp://localhost:3000"}
            />
          </Field>
        </FieldGroup>
      </SettingCard>
    )
  }

  function renderModelTestCard() {
    return (
      <SettingCard icon={TestTubeDiagonal} title={titleForLocale(locale, "模型测试", "Model test")}>
        <FieldGroup>
          <Field>
            <FieldLabel>{titleForLocale(locale, "预设问题", "Preset prompts")}</FieldLabel>
            <Textarea
              className="min-h-[132px]"
              value={draft.modelTestPrompts}
              onChange={(event) => setDraftValue("modelTestPrompts", event.target.value)}
              placeholder={DEFAULT_MODEL_TEST_PROMPTS.join("\n")}
            />
          </Field>
        </FieldGroup>
      </SettingCard>
    )
  }

  function renderCircuitCard() {
    return (
      <SettingCard icon={ShieldAlert} title={titleForLocale(locale, "熔断器", "Circuit breaker")}>
        <FieldGroup>
          <Field>
            <FieldLabel>{titleForLocale(locale, "失败阈值", "Failure threshold")}</FieldLabel>
            <Input type="number" min="0" value={draft.circuitBreakerThreshold} onChange={(event) => setDraftValue("circuitBreakerThreshold", event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>{titleForLocale(locale, "基础冷却秒数", "Cooldown seconds")}</FieldLabel>
            <Input type="number" min="0" value={draft.circuitBreakerCooldown} onChange={(event) => setDraftValue("circuitBreakerCooldown", event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>{titleForLocale(locale, "最大冷却秒数", "Max cooldown seconds")}</FieldLabel>
            <Input type="number" min="0" value={draft.circuitBreakerMaxCooldown} onChange={(event) => setDraftValue("circuitBreakerMaxCooldown", event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>{titleForLocale(locale, "健康窗口秒数", "Health window seconds")}</FieldLabel>
            <Input type="number" min="1" value={draft.healthWindowSeconds} onChange={(event) => setDraftValue("healthWindowSeconds", event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>{titleForLocale(locale, "健康惩罚权重", "Health penalty weight")}</FieldLabel>
            <Input type="number" min="0" step="0.1" value={draft.healthPenaltyWeight} onChange={(event) => setDraftValue("healthPenaltyWeight", event.target.value)} />
          </Field>
          <Field>
            <FieldLabel>{titleForLocale(locale, "健康最小样本数", "Health min samples")}</FieldLabel>
            <Input type="number" min="1" value={draft.healthMinSamples} onChange={(event) => setDraftValue("healthMinSamples", event.target.value)} />
          </Field>
        </FieldGroup>
      </SettingCard>
    )
  }

  return (
    <section className="flex min-w-0 flex-col gap-4">
      <div className="flex min-w-0 flex-col gap-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <h1 className="text-xl font-semibold text-foreground">{titleForLocale(locale, "系统设置", "Settings")}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" type="button" onClick={() => void refresh()}>
              <RotateCcw data-icon="inline-start" />
              <span className="hidden sm:inline">{titleForLocale(locale, "刷新", "Refresh")}</span>
            </Button>
            <Button type="button" disabled={saving} onClick={() => void submitSettings()}>
              <Save data-icon="inline-start" />
              {saveButtonLabel(locale, saving)}
            </Button>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          {renderAppearanceCard()}
          {renderAccountCard()}
          {renderTimeCard()}
          {renderSystemCard()}
          {renderModelTestCard()}
          <div className="xl:col-span-2">{renderCircuitCard()}</div>
        </div>
      </div>
    </section>
  )
}
