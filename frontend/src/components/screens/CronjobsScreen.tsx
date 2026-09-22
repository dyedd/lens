import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListChecks, Play, RotateCcw, ToggleLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { SettingsSection } from "@/components/settings/settingsLayout";
import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { Button } from "@/components/ui/Button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { CronjobItem, CronjobRunResult } from "@/lib/api/cronjobs";
import type { SettingItem } from "@/lib/api/settings";
import { titleForLocale, useI18n } from "@/lib/I18nContext";

import { CronjobEditDialog } from "./cronjobs/CronjobEditDialog";
import { CronjobsTable } from "./cronjobs/CronjobsTable";
import {
  coerceRetentionDays,
  intervalHours,
  parseRetentionSettings,
  RELAY_LOG_KEEP_ENABLED,
  RELAY_LOG_KEEP_PERIOD,
  REQUEST_LOG_PRUNE_TASK_ID,
  type RetentionDraft,
  runAtTime,
  type TaskDraft,
} from "./cronjobs/cronjobDrafts";

function schedulePayload(task: CronjobItem, enabled = task.enabled) {
  return {
    enabled,
    schedule_type: task.schedule_type,
    interval_hours: task.interval_hours,
    run_at_time: task.schedule_type === "interval" ? null : task.run_at_time,
    weekdays: task.schedule_type === "weekly" ? task.weekdays : [],
  };
}

function draftPayload(draft: TaskDraft, enabled: boolean) {
  return {
    enabled,
    schedule_type: draft.scheduleType,
    interval_hours: intervalHours(draft),
    run_at_time: draft.scheduleType === "interval" ? null : runAtTime(draft),
    weekdays: draft.scheduleType === "weekly" ? draft.weekdays.map(Number) : [],
  };
}

/** Render cron job schedules and manual run controls. */
export function CronjobsScreen() {
  const queryClient = useQueryClient();
  const { locale, t } = useI18n();
  const timeZone = useAppTimeZone();
  const [editingTask, setEditingTask] = useState<CronjobItem | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkEnabled, setBulkEnabled] = useState<"enabled" | "disabled" | "">(
    "",
  );
  const [bulkBusy, setBulkBusy] = useState(false);
  const tasksQuery = useQuery({
    queryKey: ["cronjobs"],
    queryFn: () => apiRequest<CronjobItem[]>("/admin/cronjobs"),
    staleTime: 10_000,
  });
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 5 * 60_000,
  });
  const tasks = tasksQuery.data ?? [];
  const selectedTasks = tasks.filter((task) => selected.has(task.id));
  const retentionDraft = parseRetentionSettings(settingsQuery.data);

  function handleSelectAll(checked: boolean) {
    setSelected(checked ? new Set(tasks.map((task) => task.id)) : new Set());
  }

  function handleSelectOne(taskId: string, checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(taskId);
      else next.delete(taskId);
      return next;
    });
  }

  const updateTask = useMutation({
    mutationFn: async ({
      task,
      payload,
      retention,
    }: {
      task: CronjobItem;
      payload: ReturnType<typeof schedulePayload>;
      retention?: RetentionDraft;
    }) => {
      const updatedTask = await apiRequest<CronjobItem>(
        `/admin/cronjobs/${encodeURIComponent(task.id)}`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
      );
      if (task.id !== REQUEST_LOG_PRUNE_TASK_ID || !retention) {
        return { task: updatedTask, settings: undefined };
      }
      const settings = await apiRequest<SettingItem[]>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({
          items: [
            {
              key: RELAY_LOG_KEEP_ENABLED,
              value: retention.enabled ? "true" : "false",
            },
            {
              key: RELAY_LOG_KEEP_PERIOD,
              value: coerceRetentionDays(retention.period),
            },
          ],
        }),
      });
      return { task: updatedTask, settings };
    },
    onSuccess: (result) => {
      queryClient.setQueryData<CronjobItem[]>(["cronjobs"], (current) =>
        (current ?? []).map((item) =>
          item.id === result.task.id ? result.task : item,
        ),
      );
      if (result.settings) {
        queryClient.setQueryData(["settings"], result.settings);
      }
      setEditingTask(null);
      toast.success(titleForLocale(locale, "定时任务已保存", "Cron job saved"));
    },
    onError: (error) => {
      void queryClient.invalidateQueries({ queryKey: ["cronjobs"] });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(locale, "保存定时任务失败", "Failed to save cron job"),
        ),
      );
    },
  });

  const runTask = useMutation({
    mutationFn: (task: CronjobItem) =>
      apiRequest<CronjobRunResult>(
        `/admin/cronjobs/${encodeURIComponent(task.id)}/runs`,
        { method: "POST" },
      ),
    onSuccess: (result) => {
      queryClient.setQueryData<CronjobItem[]>(["cronjobs"], (current) =>
        (current ?? []).map((item) =>
          item.id === result.cronjob.id ? result.cronjob : item,
        ),
      );
      toast.success(titleForLocale(locale, "定时任务已执行", "Cron job ran"));
    },
    onError: (error) =>
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(locale, "执行定时任务失败", "Failed to run cron job"),
        ),
      ),
  });

  async function bulkSetEnabled(enabled: boolean) {
    const items = selectedTasks.filter((task) => task.enabled !== enabled);
    if (!items.length) {
      setSelected(new Set());
      return;
    }
    setBulkBusy(true);
    try {
      for (const task of items) {
        const updated = await apiRequest<CronjobItem>(
          `/admin/cronjobs/${encodeURIComponent(task.id)}`,
          {
            method: "PUT",
            body: JSON.stringify(schedulePayload(task, enabled)),
          },
        );
        queryClient.setQueryData<CronjobItem[]>(["cronjobs"], (current) =>
          (current ?? []).map((item) =>
            item.id === updated.id ? updated : item,
          ),
        );
      }
      toast.success(
        titleForLocale(
          locale,
          `已${enabled ? "启用" : "停用"} ${items.length} 个定时任务`,
          `${enabled ? "Enabled" : "Disabled"} ${items.length} cron jobs`,
        ),
      );
      setSelected(new Set());
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(
            locale,
            "批量更新定时任务失败",
            "Failed to update cron jobs",
          ),
        ),
      );
      await queryClient.invalidateQueries({ queryKey: ["cronjobs"] });
    } finally {
      setBulkBusy(false);
    }
  }

  async function bulkRun() {
    const items = selectedTasks.filter((task) => task.status !== "running");
    if (!items.length) {
      setSelected(new Set());
      return;
    }
    setBulkBusy(true);
    try {
      for (const task of items) {
        const result = await apiRequest<CronjobRunResult>(
          `/admin/cronjobs/${encodeURIComponent(task.id)}/runs`,
          { method: "POST" },
        );
        queryClient.setQueryData<CronjobItem[]>(["cronjobs"], (current) =>
          (current ?? []).map((item) =>
            item.id === result.cronjob.id ? result.cronjob : item,
          ),
        );
      }
      toast.success(
        titleForLocale(
          locale,
          `已执行 ${items.length} 个定时任务`,
          `Ran ${items.length} cron jobs`,
        ),
      );
      setSelected(new Set());
    } catch (error) {
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(
            locale,
            "批量执行定时任务失败",
            "Failed to run cron jobs",
          ),
        ),
      );
      await queryClient.invalidateQueries({ queryKey: ["cronjobs"] });
    } finally {
      setBulkBusy(false);
    }
  }

  const pageError = tasksQuery.isError
    ? tasksQuery.error
    : settingsQuery.isError
      ? settingsQuery.error
      : null;
  useEffect(() => {
    if (!pageError) return;
    toast.error(
      tasksQuery.isError
        ? titleForLocale(locale, "定时任务加载失败", "Failed to load cron jobs")
        : titleForLocale(
            locale,
            "定时任务设置加载失败",
            "Failed to load cron job settings",
          ),
      {
        id: "cronjobs-load-error",
        description:
          pageError instanceof Error
            ? pageError.message
            : titleForLocale(
                locale,
                "无法读取定时任务",
                "Unable to read cron jobs",
              ),
      },
    );
  }, [locale, pageError, tasksQuery.isError]);

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["cronjobs"] }),
      queryClient.invalidateQueries({ queryKey: ["settings"] }),
    ]);
  }

  return (
    <>
      <DashboardHeaderActions>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              type="button"
              aria-label={t.refresh}
              onClick={() => void refresh()}
              disabled={tasksQuery.isFetching || settingsQuery.isFetching}
            >
              <RotateCcw data-icon="inline-start" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" align="end">
            {t.refresh}
          </TooltipContent>
        </Tooltip>
      </DashboardHeaderActions>
      <SettingsSection
        title={titleForLocale(locale, "定时任务", "Cron jobs")}
        actions={
          <Popover>
            <PopoverTrigger asChild>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none hover:bg-muted hover:text-foreground data-[state=open]:bg-muted data-[state=open]:text-foreground"
                disabled={selectedTasks.length === 0 || bulkBusy}
                aria-label={titleForLocale(locale, "批量", "Bulk")}
              >
                <ListChecks className="size-3.5" />
                <span>{titleForLocale(locale, "批量", "Bulk")}</span>
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-[240px] p-2">
              <p className="flex h-7 items-center px-2 text-[11px] text-muted-foreground">
                {titleForLocale(
                  locale,
                  `已选 ${selectedTasks.length} 项`,
                  `${selectedTasks.length} selected`,
                )}
              </p>
              <div className="flex h-7 w-full items-center gap-1.5">
                <Button
                  type="button"
                  variant="ghost"
                  className="h-7 w-16 shrink-0 justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted"
                  disabled={!bulkEnabled || bulkBusy}
                  onClick={() => {
                    void bulkSetEnabled(bulkEnabled === "enabled");
                  }}
                >
                  <ToggleLeft className="size-3" />
                  {titleForLocale(locale, "应用", "Apply")}
                </Button>
                <Select
                  value={bulkEnabled || undefined}
                  onValueChange={(value) =>
                    setBulkEnabled(value as "enabled" | "disabled")
                  }
                >
                  <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                    <SelectValue
                      placeholder={titleForLocale(locale, "状态", "Status")}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="enabled">
                      {titleForLocale(locale, "启用", "Enable")}
                    </SelectItem>
                    <SelectItem value="disabled">
                      {titleForLocale(locale, "停用", "Disable")}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                type="button"
                variant="ghost"
                className="mt-1 h-7 w-full justify-start gap-2 px-2 text-[11px] text-foreground/70 shadow-none hover:bg-muted hover:text-foreground"
                disabled={bulkBusy}
                onClick={() => void bulkRun()}
              >
                <Play className="size-3.5" />
                {titleForLocale(locale, "执行选中任务", "Run selected")}
              </Button>
            </PopoverContent>
          </Popover>
        }
      >
        <CronjobsTable
          locale={locale}
          tasks={tasks}
          isFetching={tasksQuery.isFetching}
          tasksIsError={tasksQuery.isError}
          timeZone={timeZone}
          selected={selected}
          bulkBusy={bulkBusy}
          togglingTaskId={
            updateTask.isPending && !editingTask
              ? updateTask.variables?.task.id
              : undefined
          }
          runningTaskId={runTask.isPending ? runTask.variables?.id : undefined}
          onSelectAll={handleSelectAll}
          onSelectOne={handleSelectOne}
          onEdit={setEditingTask}
          onRun={(task) => runTask.mutate(task)}
          onToggleEnabled={(task, enabled) =>
            updateTask.mutate({
              task,
              payload: schedulePayload(task, enabled),
            })
          }
        />
      </SettingsSection>
      {editingTask ? (
        <CronjobEditDialog
          key={editingTask.id}
          locale={locale}
          task={editingTask}
          retention={retentionDraft}
          saving={updateTask.isPending}
          onClose={() => setEditingTask(null)}
          onSave={(task, draft, retention) =>
            updateTask.mutate({
              task,
              payload: draftPayload(draft, task.enabled),
              retention:
                task.id === REQUEST_LOG_PRUNE_TASK_ID ? retention : undefined,
            })
          }
        />
      ) : null}
    </>
  );
}
