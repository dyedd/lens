"use client"

import { startTransition, useMemo, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { enUS, zhCN } from "date-fns/locale"
import {
  Check,
  ChevronsUpDown,
  Copy,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { Card, CardContent } from "@/components/ui/card"
import { AppDialogContent, Dialog, DialogFooter } from "@/components/ui/dialog"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  ApiError,
  type GatewayApiKey,
  type GatewayApiKeyPayload,
  type ModelGroup,
  type ProtocolKind,
  apiRequest,
} from "@/lib/api"
import { useAppTimeZone } from "@/hooks/use-app-time-zone"
import { type Locale } from "@/lib/i18n"
import { cn } from "@/lib/utils"

type GatewayApiKeyForm = {
  remark: string
  enabled: boolean
  restrictModels: boolean
  allowedModels: string[]
  maxCostUsd: string
  expiresOn?: Date
}

type GatewayModelGroupOption = {
  name: string
  protocols: ProtocolKind[]
  enabledItemCount: number
  channelNames: string[]
}

const EMPTY_FORM: GatewayApiKeyForm = {
  remark: "",
  enabled: true,
  restrictModels: false,
  allowedModels: [],
  maxCostUsd: "0",
  expiresOn: undefined,
}

const PROTOCOL_LABELS: Record<ProtocolKind, [string, string]> = {
  openai_chat: ["OpenAI Chat", "OpenAI Chat"],
  openai_responses: ["OpenAI Responses", "OpenAI Responses"],
  openai_embedding: ["OpenAI Embedding", "OpenAI Embedding"],
  anthropic: ["Anthropic", "Anthropic"],
  gemini: ["Gemini", "Gemini"],
}

function titleForLocale(locale: Locale, zh: string, en: string) {
  return locale === "zh-CN" ? zh : en
}

function maskGatewayKey(value: string) {
  if (!value) {
    return ""
  }
  if (value.length <= 12) {
    return value[0] + "*".repeat(Math.max(value.length - 2, 1)) + value.slice(-1)
  }
  return value.slice(0, 8) + "*".repeat(Math.max(value.length - 16, 8)) + value.slice(-8)
}

function getTimeZoneDateParts(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date)
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? ""
  return {
    year: Number(value("year")),
    month: Number(value("month")),
    day: Number(value("day")),
  }
}

function getTimeZoneOffsetMs(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date)
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? "0"
  const asUtc = Date.UTC(
    Number(value("year")),
    Number(value("month")) - 1,
    Number(value("day")),
    Number(value("hour")),
    Number(value("minute")),
    Number(value("second"))
  )
  return asUtc - date.getTime()
}

function getTimeInZone(year: number, month: number, day: number, hour: number, minute: number, second: number, millisecond: number, timeZone: string) {
  const utcGuess = new Date(Date.UTC(year, month, day, hour, minute, second, millisecond))
  const offset = getTimeZoneOffsetMs(utcGuess, timeZone)
  return new Date(utcGuess.getTime() - offset)
}

function parseGatewayExpiresAt(value: string | null | undefined, timeZone: string) {
  if (!value) {
    return { expiresOn: undefined }
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return { expiresOn: undefined }
  }
  const parts = getTimeZoneDateParts(date, timeZone)
  if (!parts.year || !parts.month || !parts.day) {
    return { expiresOn: undefined }
  }
  return {
    expiresOn: new Date(parts.year, parts.month - 1, parts.day),
  }
}

function formatExpiresAt(date: Date | undefined, timeZone: string) {
  if (!date) {
    return null
  }
  const nextDate = getTimeInZone(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
    23,
    59,
    59,
    999,
    timeZone
  )
  if (Number.isNaN(nextDate.getTime())) {
    return null
  }
  return nextDate.toISOString()
}

function toGatewayApiKeyForm(item: GatewayApiKey | undefined, timeZone: string): GatewayApiKeyForm {
  if (!item) {
    return { ...EMPTY_FORM }
  }
  const expires = parseGatewayExpiresAt(item.expires_at, timeZone)
  return {
    remark: item.remark,
    enabled: item.enabled,
    restrictModels: item.allowed_models.length > 0,
    allowedModels: [...item.allowed_models],
    maxCostUsd: String(item.max_cost_usd),
    expiresOn: expires.expiresOn,
  }
}

function toGatewayApiKeyPayload(form: GatewayApiKeyForm, timeZone: string): GatewayApiKeyPayload {
  return {
    remark: form.remark.trim(),
    enabled: form.enabled,
    allowed_models: form.restrictModels ? form.allowedModels : [],
    max_cost_usd: Math.max(Number(form.maxCostUsd || "0") || 0, 0),
    expires_at: formatExpiresAt(form.expiresOn, timeZone),
  }
}

function formatGatewayAmount(locale: Locale, value: number) {
  return new Intl.NumberFormat(locale === "zh-CN" ? "zh-CN" : "en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  }).format(value)
}

function formatGatewayLimit(locale: Locale, item: GatewayApiKey) {
  if (item.max_cost_usd > 0) {
    return `${formatGatewayAmount(locale, item.spent_cost_usd)} / ${formatGatewayAmount(locale, item.max_cost_usd)} USD`
  }
  return titleForLocale(locale, "不限额", "Unlimited")
}

function formatDateTime(locale: Locale, value?: string | null, timeZone?: string) {
  if (!value) {
    return titleForLocale(locale, "未设置", "Not set")
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString(locale === "zh-CN" ? "zh-CN" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    ...(timeZone ? { timeZone } : {}),
  })
}

function formatDateOnly(locale: Locale, value?: string | null, timeZone?: string) {
  if (!value) {
    return titleForLocale(locale, "未设置", "Not set")
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleDateString(locale === "zh-CN" ? "zh-CN" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(timeZone ? { timeZone } : {}),
  })
}

function formatDateLabel(locale: Locale, value?: Date) {
  if (!value) {
    return titleForLocale(locale, "选择日期", "Pick a date")
  }
  return format(value, locale === "zh-CN" ? "PPP" : "PP", {
    locale: locale === "zh-CN" ? zhCN : enUS,
  })
}

function isGatewayKeyExpired(item: GatewayApiKey) {
  if (!item.expires_at) {
    return false
  }
  const expiresAt = new Date(item.expires_at)
  if (Number.isNaN(expiresAt.getTime())) {
    return true
  }
  return expiresAt.getTime() <= Date.now()
}

function isGatewayKeyOutOfBalance(item: GatewayApiKey) {
  return item.max_cost_usd > 0 && item.spent_cost_usd >= item.max_cost_usd
}

function buildGatewayModelGroupOptions(groups: ModelGroup[]) {
  const mapping = new Map<string, GatewayModelGroupOption>()

  for (const group of groups) {
    if (group.route_group_id) {
      continue
    }
    const enabledItems = group.items.filter((item) => item.enabled)
    if (enabledItems.length === 0) {
      continue
    }
    const current =
      mapping.get(group.name) ??
      ({
        name: group.name,
        protocols: [],
        enabledItemCount: 0,
        channelNames: [],
      } satisfies GatewayModelGroupOption)

    if (!current.protocols.includes(group.protocol)) {
      current.protocols = [...current.protocols, group.protocol]
    }
    current.enabledItemCount += enabledItems.length
    current.channelNames = Array.from(
      new Set([...current.channelNames, ...enabledItems.map((item) => item.channel_name).filter(Boolean)])
    )
    mapping.set(group.name, current)
  }

  return [...mapping.values()].sort((left, right) => left.name.localeCompare(right.name))
}

function protocolSummary(locale: Locale, protocols: ProtocolKind[]) {
  return protocols
    .map((protocol) => {
      const labels = PROTOCOL_LABELS[protocol]
      return locale === "zh-CN" ? labels[0] : labels[1]
    })
    .join(" / ")
}

export function GatewayApiKeyManager({ locale }: { locale: Locale }) {
  const queryClient = useQueryClient()
  const timeZone = useAppTimeZone()
  const { data: gatewayKeys = [] } = useQuery({
    queryKey: ["gateway-api-keys"],
    queryFn: () => apiRequest<GatewayApiKey[]>("/admin/gateway-api-keys"),
    staleTime: 5 * 60_000,
  })
  const { data: modelGroups = [] } = useQuery({
    queryKey: ["model-groups"],
    queryFn: () => apiRequest<ModelGroup[]>("/admin/model-groups"),
    staleTime: 5 * 60_000,
  })

  const modelGroupOptions = useMemo(
    () => buildGatewayModelGroupOptions(modelGroups),
    [modelGroups]
  )

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingKeyId, setEditingKeyId] = useState<string | null>(null)
  const [form, setForm] = useState<GatewayApiKeyForm>({ ...EMPTY_FORM })
  const [submitting, setSubmitting] = useState(false)
  const [removingKeyId, setRemovingKeyId] = useState("")
  const [togglingKeyId, setTogglingKeyId] = useState("")
  const [copiedKey, setCopiedKey] = useState("")
  const [pickerOpen, setPickerOpen] = useState(false)

  const permissionSummary = !form.restrictModels
    ? titleForLocale(locale, "全部当前模型组", "All current model groups")
    : form.allowedModels.length > 0
      ? form.allowedModels.join(", ")
      : titleForLocale(locale, "请选择模型组", "Select model groups")

  function openCreateDialog() {
    setEditingKeyId(null)
    setForm({ ...EMPTY_FORM })
    setPickerOpen(false)
    setDialogOpen(true)
  }

  function openEditDialog(item: GatewayApiKey) {
    setEditingKeyId(item.id)
    setForm(toGatewayApiKeyForm(item, timeZone))
    setPickerOpen(false)
    setDialogOpen(true)
  }

  function updateForm<K extends keyof GatewayApiKeyForm>(
    key: K,
    value: GatewayApiKeyForm[K]
  ) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function toggleAllowedModel(name: string) {
    startTransition(() => {
      setForm((current) => {
        const exists = current.allowedModels.includes(name)
        return {
          ...current,
          allowedModels: exists
            ? current.allowedModels.filter((item) => item !== name)
            : [...current.allowedModels, name].sort((left, right) =>
                left.localeCompare(right)
              ),
        }
      })
    })
  }

  async function copyGatewayKey(value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setCopiedKey(value)
      toast.success(titleForLocale(locale, "API Key 已复制", "API key copied"))
      window.setTimeout(() => {
        setCopiedKey((current) => (current === value ? "" : current))
      }, 1500)
    } catch {
      toast.error(titleForLocale(locale, "复制失败", "Failed to copy"))
    }
  }

  async function submitGatewayKey() {
    if (form.restrictModels && form.allowedModels.length === 0) {
      toast.error(
        titleForLocale(locale, "至少选择一个模型组", "Select at least one model group")
      )
      return
    }

    setSubmitting(true)
    try {
      const payload = toGatewayApiKeyPayload(form, timeZone)
      if (editingKeyId) {
        await apiRequest<GatewayApiKey>(`/admin/gateway-api-keys/${editingKeyId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        })
      } else {
        await apiRequest<GatewayApiKey>("/admin/gateway-api-keys", {
          method: "POST",
          body: JSON.stringify(payload),
        })
      }
      toast.success(
        titleForLocale(
          locale,
          editingKeyId ? "API Key 已更新" : "API Key 已创建",
          editingKeyId ? "API key updated" : "API key created"
        )
      )
      setDialogOpen(false)
      setPickerOpen(false)
      await queryClient.invalidateQueries({ queryKey: ["gateway-api-keys"] })
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(
              locale,
              editingKeyId ? "更新 API Key 失败" : "创建 API Key 失败",
              editingKeyId ? "Failed to update API key" : "Failed to create API key"
            )
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  async function removeGatewayKey(keyId: string) {
    const confirmed = window.confirm(
      titleForLocale(locale, "确认删除此 API Key？", "Delete this API key?")
    )
    if (!confirmed) {
      return
    }

    setRemovingKeyId(keyId)
    try {
      await apiRequest<void>(`/admin/gateway-api-keys/${keyId}`, {
        method: "DELETE",
      })
      toast.success(titleForLocale(locale, "API Key 已删除", "API key deleted"))
      await queryClient.invalidateQueries({ queryKey: ["gateway-api-keys"] })
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(locale, "删除 API Key 失败", "Failed to delete API key")
      toast.error(message)
    } finally {
      setRemovingKeyId("")
    }
  }

  async function toggleGatewayKeyEnabled(item: GatewayApiKey, enabled: boolean) {
    if (togglingKeyId === item.id || removingKeyId === item.id || item.enabled === enabled) {
      return
    }

    setTogglingKeyId(item.id)
    try {
      const updated = await apiRequest<GatewayApiKey>(`/admin/gateway-api-keys/${item.id}`, {
        method: "PUT",
        body: JSON.stringify({
          remark: item.remark,
          enabled,
          allowed_models: item.allowed_models,
          max_cost_usd: item.max_cost_usd,
          expires_at: item.expires_at ?? null,
        } satisfies GatewayApiKeyPayload),
      })
      queryClient.setQueryData<GatewayApiKey[]>(["gateway-api-keys"], (current) =>
        (current ?? []).map((entry) => (entry.id === updated.id ? updated : entry))
      )
      toast.success(
        titleForLocale(
          locale,
          enabled ? "API Key 已启用" : "API Key 已停用",
          enabled ? "API key enabled" : "API key disabled"
        )
      )
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(locale, "更新 API Key 状态失败", "Failed to update API key status")
      toast.error(message)
    } finally {
      setTogglingKeyId("")
    }
  }

  return (
    <>
      <Card className="min-w-0 py-0">
        <CardContent className="flex min-w-0 flex-col gap-4 px-3 py-3 sm:px-5 sm:py-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-muted-foreground">
              {titleForLocale(locale, `共 ${gatewayKeys.length} 个密钥`, `${gatewayKeys.length} keys`)}
            </div>
            <Button type="button" onClick={openCreateDialog}>
              <Plus data-icon="inline-start" />
              {titleForLocale(locale, "创建 Key", "Create key")}
            </Button>
          </div>

          <div className="min-w-0 rounded-lg border">
            <Table className="min-w-[1120px] table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-40">{titleForLocale(locale, "密钥名称", "Key name")}</TableHead>
                  <TableHead className="w-[420px]">{titleForLocale(locale, "密钥", "Key")}</TableHead>
                  <TableHead className="w-44">{titleForLocale(locale, "限额", "Limit")}</TableHead>
                  <TableHead className="w-44">{titleForLocale(locale, "创建时间", "Created")}</TableHead>
                  <TableHead className="w-56">{titleForLocale(locale, "权限", "Permissions")}</TableHead>
                  <TableHead className="w-36 text-right">
                    {titleForLocale(locale, "操作", "Actions")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {gatewayKeys.length > 0 ? (
                  gatewayKeys.map((item) => {
                    const isBusy = removingKeyId === item.id || togglingKeyId === item.id
                    const expired = isGatewayKeyExpired(item)
                    const outOfBalance = isGatewayKeyOutOfBalance(item)
                    return (
                      <TableRow key={item.id}>
                        <TableCell className="min-w-0">
                          <div className="flex min-w-36 flex-col gap-2">
                            <div className="truncate text-sm text-foreground">
                              {item.remark || titleForLocale(locale, "未命名", "Unnamed")}
                            </div>
                            {expired || outOfBalance ? (
                              <div className="flex flex-wrap gap-1">
                                {expired ? (
                                  <Badge variant="destructive">
                                    {titleForLocale(locale, "已过期", "Expired")}
                                  </Badge>
                                ) : null}
                                {outOfBalance ? (
                                  <Badge variant="destructive">
                                    {titleForLocale(locale, "已超额", "Limit reached")}
                                  </Badge>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="min-w-0">
                          <div className="flex min-w-0 items-center gap-2">
                            <div className="min-w-0 flex-1">
                              <div className="truncate font-mono text-sm text-foreground">
                                {maskGatewayKey(item.api_key)}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {titleForLocale(
                                  locale,
                                  `已用 ${formatGatewayAmount(locale, item.spent_cost_usd)} USD`,
                                  `Used ${formatGatewayAmount(locale, item.spent_cost_usd)} USD`
                                )}
                              </div>
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => void copyGatewayKey(item.api_key)}
                              title={titleForLocale(locale, "复制", "Copy")}
                            >
                              {copiedKey === item.api_key ? <Check /> : <Copy />}
                            </Button>
                          </div>
                        </TableCell>
                        <TableCell className="min-w-0">
                          <div className="flex min-w-0 flex-col gap-1">
                            <div>{formatGatewayLimit(locale, item)}</div>
                            <div className="text-xs text-muted-foreground">
                              {item.expires_at
                                ? titleForLocale(
                                    locale,
                                    `到期 ${formatDateOnly(locale, item.expires_at, timeZone)}`,
                                    `Expires ${formatDateOnly(locale, item.expires_at, timeZone)}`
                                  )
                                : titleForLocale(locale, "永不过期", "No expiry")}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDateTime(locale, item.created_at, timeZone)}
                        </TableCell>
                        <TableCell className="min-w-0">
                          {item.allowed_models.length > 0 ? (
                            <div className="flex max-w-56 flex-wrap gap-1">
                              {item.allowed_models.slice(0, 2).map((modelName) => (
                                <Badge key={modelName} variant="outline">
                                  {modelName}
                                </Badge>
                              ))}
                              {item.allowed_models.length > 2 ? (
                                <Badge variant="outline">
                                  +{item.allowed_models.length - 2}
                                </Badge>
                              ) : null}
                            </div>
                          ) : (
                            <Badge variant="secondary">
                              {titleForLocale(locale, "全部模型组", "All model groups")}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center justify-end gap-3">
                            <Switch
                              checked={item.enabled}
                              onCheckedChange={(checked) => void toggleGatewayKeyEnabled(item, Boolean(checked))}
                              title={titleForLocale(
                                locale,
                                item.enabled ? "点击停用" : "点击启用",
                                item.enabled ? "Click to disable" : "Click to enable"
                              )}
                              aria-label={titleForLocale(
                                locale,
                                item.enabled ? "停用 API Key" : "启用 API Key",
                                item.enabled ? "Disable API key" : "Enable API key"
                              )}
                              disabled={isBusy}
                            />
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => openEditDialog(item)}
                              title={titleForLocale(locale, "编辑", "Edit")}
                              disabled={isBusy}
                            >
                              <Pencil />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                              onClick={() => void removeGatewayKey(item.id)}
                              title={titleForLocale(locale, "删除", "Delete")}
                              disabled={isBusy}
                            >
                              <Trash2 />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">
                      {titleForLocale(locale, "当前没有 API 密钥", "No API keys")}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open)
          if (!open) {
            setPickerOpen(false)
          }
        }}
      >
        <AppDialogContent
          className="sm:max-w-xl"
          title={titleForLocale(
            locale,
            editingKeyId ? "编辑 API Key" : "创建 API Key",
            editingKeyId ? "Edit API key" : "Create API key"
          )}
        >
          <div className="flex flex-col gap-4">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="gateway-key-remark">
                  {titleForLocale(locale, "密钥名称", "Key name")}
                </FieldLabel>
                <Input
                  id="gateway-key-remark"
                  value={form.remark}
                  onChange={(event) => updateForm("remark", event.target.value)}
                  placeholder={titleForLocale(locale, "可留空", "Optional")}
                />
              </Field>

              <Field
                orientation="horizontal"
                className="items-center justify-between rounded-lg border bg-muted/20 px-3 py-3"
              >
                <FieldContent>
                  <FieldLabel className="w-auto">
                    {titleForLocale(locale, "启用", "Enabled")}
                  </FieldLabel>
                  <FieldDescription>
                    {titleForLocale(
                      locale,
                      "关闭后立即拒绝该密钥请求",
                      "Reject requests immediately when disabled"
                    )}
                  </FieldDescription>
                </FieldContent>
                <Switch
                  checked={form.enabled}
                  onCheckedChange={(checked) => updateForm("enabled", Boolean(checked))}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="gateway-key-limit">
                  {titleForLocale(locale, "最大余额 (USD)", "Max balance (USD)")}
                </FieldLabel>
                <Input
                  id="gateway-key-limit"
                  type="number"
                  min="0"
                  step="0.0001"
                  value={form.maxCostUsd}
                  onChange={(event) => updateForm("maxCostUsd", event.target.value)}
                />
                <FieldDescription>
                  {titleForLocale(locale, "填 0 表示不限制", "Use 0 for unlimited")}
                </FieldDescription>
              </Field>

              <FieldSet>
                <FieldLegend variant="label">
                  {titleForLocale(locale, "允许模型组", "Allowed model groups")}
                </FieldLegend>

                <Field
                  orientation="horizontal"
                  className="items-center justify-between rounded-lg border bg-muted/20 px-3 py-3"
                >
                  <FieldContent>
                    <FieldLabel className="w-auto">
                      {titleForLocale(locale, "仅允许选定模型组", "Restrict to selected groups")}
                    </FieldLabel>
                    <FieldDescription>
                      {titleForLocale(
                        locale,
                        "关闭时可调用当前全部启用模型组",
                        "Disabled means the key can use every enabled model group"
                      )}
                    </FieldDescription>
                  </FieldContent>
                  <Switch
                    checked={form.restrictModels}
                    onCheckedChange={(checked) => {
                      startTransition(() => {
                        setForm((current) => ({
                          ...current,
                          restrictModels: Boolean(checked),
                        }))
                      })
                    }}
                  />
                </Field>

                <Field data-disabled={!form.restrictModels}>
                  <FieldLabel>
                    {titleForLocale(locale, "模型组", "Model groups")}
                  </FieldLabel>
                  <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
                    <PopoverTrigger asChild>
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full justify-between"
                        disabled={!form.restrictModels}
                      >
                        <span className="truncate text-left">{permissionSummary}</span>
                        <ChevronsUpDown className="text-muted-foreground" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-[calc(100vw-2rem)] p-0 sm:w-[360px]">
                      <Command>
                        <CommandInput
                          placeholder={titleForLocale(
                            locale,
                            "搜索模型组...",
                            "Search model groups..."
                          )}
                        />
                        <CommandList>
                          <CommandEmpty>
                            {modelGroupOptions.length > 0
                              ? titleForLocale(
                                  locale,
                                  "没有匹配的模型组",
                                  "No matching model groups"
                                )
                              : titleForLocale(
                                  locale,
                                  "当前没有可用模型组",
                                  "No model groups available"
                                )}
                          </CommandEmpty>
                          <CommandGroup
                            heading={titleForLocale(
                              locale,
                              "当前启用模型组",
                              "Enabled model groups"
                            )}
                          >
                            {modelGroupOptions.map((option) => {
                              const checked = form.allowedModels.includes(option.name)
                              return (
                                <CommandItem
                                  key={option.name}
                                  value={`${option.name} ${protocolSummary(locale, option.protocols)} ${option.channelNames.join(" ")}`}
                                  onSelect={() => toggleAllowedModel(option.name)}
                                  className="items-start gap-3"
                                >
                                  <Checkbox checked={checked} className="mt-0.5 pointer-events-none" />
                                  <div className="min-w-0 flex-1">
                                    <div className="truncate font-medium text-foreground">
                                      {option.name}
                                    </div>
                                    <div className="truncate text-xs text-muted-foreground">
                                      {protocolSummary(locale, option.protocols)} ·{" "}
                                      {titleForLocale(
                                        locale,
                                        `${option.enabledItemCount} 个启用成员`,
                                        `${option.enabledItemCount} enabled members`
                                      )}
                                    </div>
                                  </div>
                                </CommandItem>
                              )
                            })}
                          </CommandGroup>
                        </CommandList>
                      </Command>
                    </PopoverContent>
                  </Popover>
                  <FieldDescription>
                    {form.restrictModels
                      ? titleForLocale(
                          locale,
                          "权限来源于当前启用模型组；留空将无法保存",
                          "Permissions come from currently enabled model groups; choose at least one"
                        )
                      : titleForLocale(
                          locale,
                          "当前为全部放行模式",
                          "The key can currently access all model groups"
                        )}
                  </FieldDescription>
                  {form.restrictModels && form.allowedModels.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {form.allowedModels.map((modelName) => (
                        <Badge key={modelName} variant="outline">
                          {modelName}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </Field>
              </FieldSet>

              <Field>
                <FieldLabel>
                  {titleForLocale(locale, "过期日期", "Expires on")}
                </FieldLabel>
                <div className="flex flex-col gap-3 md:flex-row">
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        type="button"
                        variant="outline"
                        className={cn(
                          "w-full justify-between md:flex-1",
                          !form.expiresOn && "text-muted-foreground"
                        )}
                      >
                        <span>{formatDateLabel(locale, form.expiresOn)}</span>
                        <ChevronsUpDown className="text-muted-foreground" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-auto overflow-hidden p-0">
                      <Calendar
                        mode="single"
                        selected={form.expiresOn}
                        defaultMonth={form.expiresOn}
                        onSelect={(value) => updateForm("expiresOn", value ?? undefined)}
                        locale={locale === "zh-CN" ? zhCN : enUS}
                        captionLayout="dropdown"
                      />
                    </PopoverContent>
                  </Popover>

                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => updateForm("expiresOn", undefined)}
                  >
                    {titleForLocale(locale, "清空", "Clear")}
                  </Button>
                </div>
                <FieldDescription>
                  {titleForLocale(locale, "留空表示永不过期", "Leave blank to keep the key active forever")}
                </FieldDescription>
              </Field>
            </FieldGroup>

            <DialogFooter className="mx-0 mb-0 rounded-none border-0 bg-transparent p-0 pt-2">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                {titleForLocale(locale, "取消", "Cancel")}
              </Button>
              <Button type="button" onClick={() => void submitGatewayKey()} disabled={submitting}>
                {submitting
                  ? titleForLocale(locale, "保存中...", "Saving...")
                  : titleForLocale(locale, "保存", "Save")}
              </Button>
            </DialogFooter>
          </div>
        </AppDialogContent>
      </Dialog>
    </>
  )
}
