"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Play, RotateCcw, Save } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useAppTimeZone } from "@/hooks/use-app-time-zone"
import {
  apiRequest,
  ApiError,
  type CronjobItem,
  type CronjobRunResult,
  type CronjobScheduleType,
  type SettingItem,
} from "@/lib/api"
import { formatLogDateTime } from "@/lib/datetime"
import { useI18n, type Locale } from "@/lib/i18n"

type TaskDraft = {
  enabled: boolean
  scheduleType: CronjobScheduleType
  intervalHours: string
  runAtHour: string
  runAtMinute: string
  weekdays: string[]
}

type RetentionDraft = {
  enabled: boolean
  period: string
}

const REQUEST_LOG_PRUNE_TASK_ID = "request_log_prune"
const REQUEST_LOG_STATS_PERSIST_TASK_ID = "request_log_stats_persist"
const RELAY_LOG_KEEP_ENABLED = "relay_log_keep_enabled"
const RELAY_LOG_KEEP_PERIOD = "relay_log_keep_period"

const WEEKDAYS = [
  { value: "1", zh: "一", en: "Mon" },
  { value: "2", zh: "二", en: "Tue" },
  { value: "3", zh: "三", en: "Wed" },
  { value: "4", zh: "四", en: "Thu" },
  { value: "5", zh: "五", en: "Fri" },
  { value: "6", zh: "六", en: "Sat" },
  { value: "7", zh: "日", en: "Sun" },
]

function titleForLocale(locale: Locale, zh: string, en: string) {
  return locale === "zh-CN" ? zh : en
}

function statusLabel(locale: Locale, status: CronjobItem["status"]) {
  const labels: Record<CronjobItem["status"], [string, string]> = {
    idle: ["空闲", "Idle"],
    running: ["运行中", "Running"],
    succeeded: ["成功", "Succeeded"],
    failed: ["失败", "Failed"],
    disabled: ["已停用", "Disabled"],
  }
  const [zh, en] = labels[status] ?? labels.idle
  return titleForLocale(locale, zh, en)
}

function statusVariant(status: CronjobItem["status"]) {
  if (status === "failed") {
    return "destructive" as const
  }
  if (status === "running" || status === "succeeded") {
    return "secondary" as const
  }
  return "outline" as const
}

function taskTitle(locale: Locale, task: CronjobItem) {
  const labels: Record<string, [string, string]> = {
    [REQUEST_LOG_PRUNE_TASK_ID]: ["请求日志清理", "Request log cleanup"],
    [REQUEST_LOG_STATS_PERSIST_TASK_ID]: ["请求日志统计落库", "Request log stats persist"],
    model_price_sync: ["模型价格同步", "Model price sync"],
  }
  const label = labels[task.id]
  if (!label) {
    return task.name
  }
  return titleForLocale(locale, label[0], label[1])
}

function taskDescription(locale: Locale, task: CronjobItem) {
  const labels: Record<string, [string, string]> = {
    [REQUEST_LOG_PRUNE_TASK_ID]: ["按日志保留天数清理过期请求日志", "Prune request logs by the retention window"],
    [REQUEST_LOG_STATS_PERSIST_TASK_ID]: ["归档请求日志统计数据", "Persist request log statistics"],
    model_price_sync: ["从 models.dev 同步模型价格", "Sync model prices from models.dev"],
  }
  const label = labels[task.id]
  if (!label) {
    return task.description
  }
  return titleForLocale(locale, label[0], label[1])
}

function formatTaskTime(locale: Locale, value: string | null | undefined, timeZone: string) {
  if (!value) {
    return titleForLocale(locale, "未执行", "Never")
  }
  return formatLogDateTime(value, locale, timeZone)
}

function intervalHours(draft: TaskDraft) {
  return Number(draft.intervalHours)
}

function sortedWeekdays(values: string[]) {
  return [...new Set(values)].sort((left, right) => Number(left) - Number(right))
}

function splitRunAtTime(value: string | null | undefined) {
  const [hour = "03", minute = "00"] = (value || "03:00").split(":", 2)
  return {
    runAtHour: hour.padStart(2, "0").slice(0, 2),
    runAtMinute: minute.padStart(2, "0").slice(0, 2),
  }
}

function runAtTime(draft: TaskDraft) {
  return `${draft.runAtHour}:${draft.runAtMinute}`
}

function taskDraft(item: CronjobItem): TaskDraft {
  const runAt = splitRunAtTime(item.run_at_time)
  return {
    enabled: item.enabled,
    scheduleType: item.schedule_type ?? "interval",
    intervalHours: String(Math.max(item.interval_hours, 1)),
    runAtHour: runAt.runAtHour,
    runAtMinute: runAt.runAtMinute,
    weekdays: sortedWeekdays((item.weekdays ?? []).map(String)),
  }
}

function parseRetentionSettings(items: SettingItem[] | undefined): RetentionDraft {
  const mapping = new Map((items ?? []).map((item) => [item.key, item.value]))
  return {
    enabled: !["0", "false", "no", "off"].includes(
      (mapping.get(RELAY_LOG_KEEP_ENABLED) ?? "true").toLowerCase()
    ),
    period: mapping.get(RELAY_LOG_KEEP_PERIOD) ?? "7",
  }
}

function retentionDays(draft: RetentionDraft) {
  return Number(draft.period)
}

function normalizeRetentionDraft(draft: RetentionDraft) {
  return {
    enabled: draft.enabled,
    period: retentionDays(draft),
  }
}

function isRetentionDraftChanged(settings: SettingItem[] | undefined, draft: RetentionDraft) {
  const current = normalizeRetentionDraft(parseRetentionSettings(settings))
  const next = normalizeRetentionDraft(draft)
  return JSON.stringify(current) !== JSON.stringify(next)
}

function isRetentionDraftInvalid(draft: RetentionDraft) {
  if (!draft.enabled) {
    return false
  }
  const days = retentionDays(draft)
  return !Number.isInteger(days) || days < 1
}

function normalizeDraftForCompare(draft: TaskDraft) {
  return {
    enabled: draft.enabled,
    scheduleType: draft.scheduleType,
    intervalHours: intervalHours(draft),
    runAtTime: draft.scheduleType === "interval" ? null : runAtTime(draft),
    weekdays: draft.scheduleType === "weekly" ? sortedWeekdays(draft.weekdays) : [],
  }
}

function isDraftChanged(item: CronjobItem, draft: TaskDraft | undefined) {
  if (!draft) {
    return false
  }
  const current = normalizeDraftForCompare(taskDraft(item))
  const next = normalizeDraftForCompare(draft)
  return JSON.stringify(current) !== JSON.stringify(next)
}

function isDraftInvalid(draft: TaskDraft) {
  const intervalNumber = Number(draft.intervalHours)
  if (
    !Number.isInteger(intervalNumber) ||
    intervalNumber < 1
  ) {
    return true
  }
  if (draft.scheduleType !== "interval" && (!draft.runAtHour || !draft.runAtMinute)) {
    return true
  }
  return draft.scheduleType === "weekly" && draft.weekdays.length === 0
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback
}

function scheduleTypeOptions(locale: Locale) {
  return [
    { value: "interval" as const, label: titleForLocale(locale, "小时", "Hourly") },
    { value: "daily" as const, label: titleForLocale(locale, "每天", "Daily") },
    { value: "weekly" as const, label: titleForLocale(locale, "每周", "Weekly") },
  ]
}

function ScheduleEditor({
  draft,
  locale,
  invalid,
  onChange,
}: {
  draft: TaskDraft
  locale: Locale
  invalid: boolean
  onChange: (value: Partial<TaskDraft>) => void
}) {
  function setRunAtTime(value: Partial<Pick<TaskDraft, "runAtHour" | "runAtMinute">>) {
    onChange(value)
  }

  return (
    <div className="mx-auto flex min-w-72 max-w-72 flex-col items-center gap-2">
      <SegmentedControl
        className="self-center"
        value={draft.scheduleType}
        onValueChange={(value) => onChange({ scheduleType: value })}
        options={scheduleTypeOptions(locale)}
      />
      {draft.scheduleType === "interval" ? (
        <div className="flex items-center justify-center gap-2">
          <span className="text-sm text-muted-foreground">{titleForLocale(locale, "每", "Every")}</span>
          <Input
            className="w-20"
            type="number"
            min="1"
            step="1"
            value={draft.intervalHours}
            aria-invalid={invalid}
            onChange={(event) => onChange({ intervalHours: event.target.value })}
          />
          <span className="text-sm text-muted-foreground">{titleForLocale(locale, "小时", "hours")}</span>
        </div>
      ) : null}
      {draft.scheduleType === "daily" ? (
        <TimeSelector
          locale={locale}
          hour={draft.runAtHour}
          minute={draft.runAtMinute}
          invalid={invalid}
          onChange={setRunAtTime}
        />
      ) : null}
      {draft.scheduleType === "weekly" ? (
        <div className="flex flex-col items-center gap-2">
          <ToggleGroup
            type="multiple"
            variant="outline"
            size="sm"
            value={draft.weekdays}
            onValueChange={(value) => onChange({ weekdays: sortedWeekdays(value) })}
            aria-label={titleForLocale(locale, "执行星期", "Run weekdays")}
          >
            {WEEKDAYS.map((weekday) => (
              <ToggleGroupItem key={weekday.value} value={weekday.value}>
                {titleForLocale(locale, weekday.zh, weekday.en)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <TimeSelector
            locale={locale}
            hour={draft.runAtHour}
            minute={draft.runAtMinute}
            invalid={invalid}
            onChange={setRunAtTime}
          />
        </div>
      ) : null}
    </div>
  )
}

function RetentionEditor({
  draft,
  locale,
  invalid,
  disabled,
  onChange,
}: {
  draft: RetentionDraft
  locale: Locale
  invalid: boolean
  disabled: boolean
  onChange: (value: Partial<RetentionDraft>) => void
}) {
  return (
    <div className="mx-auto flex min-w-52 max-w-52 flex-col items-center gap-2">
      <div className="flex items-center justify-center gap-2">
        <Switch
          checked={draft.enabled}
          disabled={disabled}
          onCheckedChange={(checked) => onChange({ enabled: checked })}
          aria-label={titleForLocale(locale, "保留日志", "Keep logs")}
        />
        <span className="text-sm text-muted-foreground">{titleForLocale(locale, "保留日志", "Keep logs")}</span>
      </div>
      <div className="flex items-center justify-center gap-2">
        <span className="text-sm text-muted-foreground">{titleForLocale(locale, "保留", "Keep")}</span>
        <Input
          className="w-20"
          type="number"
          min="1"
          step="1"
          value={draft.period}
          aria-invalid={invalid}
          disabled={disabled || !draft.enabled}
          onChange={(event) => onChange({ period: event.target.value })}
        />
        <span className="text-sm text-muted-foreground">{titleForLocale(locale, "天", "days")}</span>
      </div>
    </div>
  )
}

function TimeSelector({
  locale,
  hour,
  minute,
  invalid,
  onChange,
}: {
  locale: Locale
  hour: string
  minute: string
  invalid: boolean
  onChange: (value: Partial<Pick<TaskDraft, "runAtHour" | "runAtMinute">>) => void
}) {
  const hours = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"))
  const minutes = Array.from({ length: 12 }, (_, index) => String(index * 5).padStart(2, "0"))
  return (
    <div className="flex items-center gap-2">
      <Select value={hour} onValueChange={(value) => onChange({ runAtHour: value })}>
        <SelectTrigger className="w-16" aria-invalid={invalid} aria-label={titleForLocale(locale, "小时", "Hour")}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {hours.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <span className="text-sm text-muted-foreground">:</span>
      <Select value={minute} onValueChange={(value) => onChange({ runAtMinute: value })}>
        <SelectTrigger className="w-16" aria-invalid={invalid} aria-label={titleForLocale(locale, "分钟", "Minute")}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {minutes.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}

export function CronjobsScreen() {
  const queryClient = useQueryClient()
  const { locale, t } = useI18n()
  const timeZone = useAppTimeZone()
  const [drafts, setDrafts] = useState<Record<string, TaskDraft>>({})
  const [retentionDraftOverride, setRetentionDraftOverride] = useState<RetentionDraft | null>(null)

  const { data: tasks = [], isFetching } = useQuery({
    queryKey: ["cronjobs"],
    queryFn: () => apiRequest<CronjobItem[]>("/admin/cronjobs"),
    staleTime: 10_000,
  })

  const { data: settings, isFetching: isFetchingSettings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 5 * 60_000,
  })

  const retentionDraft = retentionDraftOverride ?? parseRetentionSettings(settings)

  const updateTask = useMutation({
    mutationFn: async (task: CronjobItem) => {
      const draft = drafts[task.id] ?? taskDraft(task)
      const updatedTask = await apiRequest<CronjobItem>("/admin/cronjobs/" + encodeURIComponent(task.id), {
        method: "PUT",
        body: JSON.stringify({
          enabled: draft.enabled,
          schedule_type: draft.scheduleType,
          interval_hours: intervalHours(draft),
          run_at_time: draft.scheduleType === "interval" ? null : runAtTime(draft),
          weekdays: draft.scheduleType === "weekly" ? draft.weekdays.map(Number) : [],
        }),
      })
      if (task.id !== REQUEST_LOG_PRUNE_TASK_ID) {
        return { task: updatedTask, settings: undefined }
      }
      const updatedSettings = await apiRequest<SettingItem[]>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({
          items: [
            { key: RELAY_LOG_KEEP_ENABLED, value: retentionDraft.enabled ? "true" : "false" },
            { key: RELAY_LOG_KEEP_PERIOD, value: retentionDraft.period.trim() || "7" },
          ],
        }),
      })
      return { task: updatedTask, settings: updatedSettings }
    },
    onSuccess: (result, task) => {
      queryClient.setQueryData<CronjobItem[]>(["cronjobs"], (current) =>
        (current ?? []).map((item) => (item.id === result.task.id ? result.task : item))
      )
      if (result.settings) {
        queryClient.setQueryData(["settings"], result.settings)
        setRetentionDraftOverride(null)
      }
      setDrafts((current) => {
        const next = { ...current }
        delete next[task.id]
        return next
      })
      toast.success(titleForLocale(locale, "定时任务已保存", "Cron job saved"))
    },
    onError: (error) => {
      void queryClient.invalidateQueries({ queryKey: ["cronjobs"] })
      void queryClient.invalidateQueries({ queryKey: ["settings"] })
      toast.error(errorMessage(error, titleForLocale(locale, "保存定时任务失败", "Failed to save cron job")))
    },
  })

  const runTask = useMutation({
    mutationFn: (task: CronjobItem) =>
      apiRequest<CronjobRunResult>("/admin/cronjobs/" + encodeURIComponent(task.id) + "/runs", {
        method: "POST",
      }),
    onSuccess: (result) => {
      queryClient.setQueryData<CronjobItem[]>(["cronjobs"], (current) =>
        (current ?? []).map((item) => (item.id === result.cronjob.id ? result.cronjob : item))
      )
      toast.success(titleForLocale(locale, "定时任务已执行", "Cron job ran"))
    },
    onError: (error) => {
      toast.error(errorMessage(error, titleForLocale(locale, "执行定时任务失败", "Failed to run cron job")))
    },
  })

  const runningTaskId = runTask.isPending ? runTask.variables?.id : undefined
  const savingTaskId = updateTask.isPending ? updateTask.variables?.id : undefined
  const hasTasks = tasks.length > 0
  function setDraftValue(task: CronjobItem, value: Partial<TaskDraft>) {
    const currentDraft = drafts[task.id] ?? taskDraft(task)
    setDrafts((current) => ({
      ...current,
      [task.id]: {
        ...currentDraft,
        ...value,
      },
    }))
  }

  function setRetentionDraftValue(value: Partial<RetentionDraft>) {
    setRetentionDraftOverride((current) => ({
      ...(current ?? retentionDraft),
      ...value,
    }))
  }

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["cronjobs"] }),
      queryClient.invalidateQueries({ queryKey: ["settings"] }),
    ])
  }

  return (
    <section className="flex min-w-0 flex-col gap-4">
      <div className="flex min-w-0 flex-col gap-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <h1 className="text-xl font-semibold text-foreground">{t.cronjobs}</h1>
          <div className="flex items-center gap-2">
            <Button variant="outline" type="button" onClick={() => void refresh()} disabled={isFetching || isFetchingSettings}>
              <RotateCcw data-icon="inline-start" />
              <span className="hidden sm:inline">{t.refresh}</span>
            </Button>
          </div>
        </div>

        <Card className="min-w-0 py-0">
          <CardContent className="min-w-0 p-3 sm:p-5">
            <Table className="min-w-[1320px] table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-64">{titleForLocale(locale, "任务", "Task")}</TableHead>
                  <TableHead className="w-16">{titleForLocale(locale, "启用", "Enabled")}</TableHead>
                  <TableHead className="w-72 text-center">{titleForLocale(locale, "计划", "Schedule")}</TableHead>
                  <TableHead className="w-56 text-center">{titleForLocale(locale, "任务配置", "Task config")}</TableHead>
                  <TableHead className="w-24">{titleForLocale(locale, "状态", "Status")}</TableHead>
                  <TableHead className="w-36">{titleForLocale(locale, "上次执行", "Last run")}</TableHead>
                  <TableHead className="w-36">{titleForLocale(locale, "下次执行", "Next run")}</TableHead>
                  <TableHead className="w-40 text-right">{titleForLocale(locale, "操作", "Actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hasTasks ? (
                  tasks.map((task) => {
                    const draft = drafts[task.id] ?? taskDraft(task)
                    const invalidDraft = isDraftInvalid(draft)
                    const retentionTask = task.id === REQUEST_LOG_PRUNE_TASK_ID
                    const waitingForRetentionSettings = retentionTask && settings === undefined
                    const invalidRetention = retentionTask && isRetentionDraftInvalid(retentionDraft)
                    const retentionChanged = retentionTask && isRetentionDraftChanged(settings, retentionDraft)
                    const changed = isDraftChanged(task, draft) || retentionChanged
                    const running = task.status === "running" || runningTaskId === task.id
                    return (
                      <TableRow key={task.id}>
                        <TableCell>
                          <div className="flex min-w-52 flex-col gap-1">
                            <span className="font-medium text-foreground">{taskTitle(locale, task)}</span>
                            <span className="max-w-80 truncate text-xs text-muted-foreground">{taskDescription(locale, task)}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Switch
                            checked={draft.enabled}
                            onCheckedChange={(checked) => setDraftValue(task, { enabled: checked })}
                            aria-label={titleForLocale(locale, "启用任务", "Enable task")}
                          />
                        </TableCell>
                        <TableCell className="text-center align-middle">
                          <ScheduleEditor
                            draft={draft}
                            locale={locale}
                            invalid={invalidDraft}
                            onChange={(value) => setDraftValue(task, value)}
                          />
                        </TableCell>
                        <TableCell className="text-center align-middle">
                          {retentionTask ? (
                            <RetentionEditor
                              draft={retentionDraft}
                              locale={locale}
                              invalid={invalidRetention}
                              disabled={waitingForRetentionSettings}
                              onChange={setRetentionDraftValue}
                            />
                          ) : (
                            <span className="text-sm text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            <Badge variant={statusVariant(task.status)}>{statusLabel(locale, task.status)}</Badge>
                            {task.last_error ? (
                              <span className="max-w-64 truncate text-xs text-muted-foreground" title={task.last_error}>
                                {task.last_error}
                              </span>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell>{formatTaskTime(locale, task.last_finished_at ?? task.last_started_at, timeZone)}</TableCell>
                        <TableCell>{formatTaskTime(locale, task.next_run_at, timeZone)}</TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={!changed || waitingForRetentionSettings || invalidDraft || invalidRetention || savingTaskId === task.id}
                              onClick={() => updateTask.mutate(task)}
                            >
                              <Save data-icon="inline-start" />
                              {titleForLocale(locale, "保存", "Save")}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={running}
                              onClick={() => runTask.mutate(task)}
                            >
                              <Play data-icon="inline-start" />
                              {running
                                ? titleForLocale(locale, "运行中", "Running")
                                : titleForLocale(locale, "运行", "Run")}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">
                      {isFetching
                        ? titleForLocale(locale, "加载中...", "Loading...")
                        : titleForLocale(locale, "暂无定时任务", "No cron jobs")}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </section>
  )
}
