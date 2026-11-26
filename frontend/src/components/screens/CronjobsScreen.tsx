import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { SelectionActionBar } from "@/components/ui/SelectionActionBar";
import { SettingsSection } from "@/components/ui/SettingsLayout";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { useRowSelection } from "@/hooks/useRowSelection";
import { getApiErrorMessage } from "@/lib/api/client";
import {
  type CronjobItem,
  requestCronjobs,
  runCronjob,
  updateCronjob,
} from "@/lib/api/cronjobs";
import { requestSettings } from "@/lib/api/settings";
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

const cronjobId = (task: CronjobItem) => task.id;

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

export function CronjobsScreen() {
  const queryClient = useQueryClient();
  const { locale, t } = useI18n();
  const timeZone = useAppTimeZone();
  const [editingTask, setEditingTask] = useState<CronjobItem | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const tasksQuery = useQuery({
    queryKey: ["cronjobs"],
    queryFn: requestCronjobs,
    staleTime: 10_000,
  });
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => requestSettings(),
    staleTime: 5 * 60_000,
  });
  const tasks = tasksQuery.data ?? [];
  const selection = useRowSelection(tasks, cronjobId);
  const selectedTasks = selection.selectedRows;
  const retentionDraft = parseRetentionSettings(settingsQuery.data);

  function updateCronjobCache(updatedTask: CronjobItem) {
    queryClient.setQueryData<CronjobItem[]>(["cronjobs"], (current) =>
      (current ?? []).map((task) =>
        task.id === updatedTask.id ? updatedTask : task,
      ),
    );
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
      const updatedTask = await updateCronjob(task.id, payload);
      if (task.id !== REQUEST_LOG_PRUNE_TASK_ID || !retention) {
        return { task: updatedTask, settings: undefined };
      }
      const settings = await requestSettings({
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
      updateCronjobCache(result.task);
      if (result.settings) {
        queryClient.setQueryData(["settings"], result.settings);
      }
      setEditingTask(null);
      toast.success(
        titleForLocale(locale, "计划任务已保存", "Scheduled task saved"),
      );
    },
    onError: (error) => {
      void queryClient.invalidateQueries({ queryKey: ["cronjobs"] });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(
            locale,
            "保存计划任务失败",
            "Failed to save scheduled task",
          ),
        ),
      );
    },
  });

  const runTask = useMutation({
    mutationFn: (task: CronjobItem) => runCronjob(task.id),
    onSuccess: (task) => {
      updateCronjobCache(task);
      toast.success(
        titleForLocale(locale, "计划任务已开始", "Scheduled task started"),
      );
    },
    onError: (error) =>
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(
            locale,
            "执行计划任务失败",
            "Failed to run scheduled task",
          ),
        ),
      ),
  });

  async function runBulkAction(
    items: CronjobItem[],
    action: (task: CronjobItem) => Promise<CronjobItem>,
    successMessage: string,
    failureMessage: string,
  ) {
    if (!items.length) {
      selection.clear();
      return;
    }
    setBulkBusy(true);
    try {
      for (const task of items) {
        const updated = await action(task);
        updateCronjobCache(updated);
      }
      toast.success(successMessage);
      selection.clear();
    } catch (error) {
      toast.error(getApiErrorMessage(error, failureMessage));
      await queryClient.invalidateQueries({ queryKey: ["cronjobs"] });
    } finally {
      setBulkBusy(false);
    }
  }

  async function bulkSetEnabled(enabled: boolean) {
    const items = selectedTasks.filter((task) => task.enabled !== enabled);
    await runBulkAction(
      items,
      (task) => updateCronjob(task.id, schedulePayload(task, enabled)),
      titleForLocale(
        locale,
        `已${enabled ? "启用" : "停用"} ${items.length} 项计划任务`,
        `${enabled ? "Enabled" : "Disabled"} ${items.length} scheduled tasks`,
      ),
      titleForLocale(
        locale,
        "批量更新计划任务失败",
        "Failed to update scheduled tasks",
      ),
    );
  }

  async function bulkRun() {
    const items = selectedTasks.filter((task) => task.status !== "running");
    await runBulkAction(
      items,
      (task) => runCronjob(task.id),
      titleForLocale(
        locale,
        `已触发执行 ${items.length} 项计划任务`,
        `Ran ${items.length} scheduled tasks`,
      ),
      titleForLocale(
        locale,
        "批量执行计划任务失败",
        "Failed to run scheduled tasks",
      ),
    );
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
        ? titleForLocale(
            locale,
            "计划任务加载失败",
            "Failed to load scheduled tasks",
          )
        : titleForLocale(
            locale,
            "计划任务设置加载失败",
            "Failed to load scheduled task settings",
          ),
      {
        id: "cronjobs-load-error",
        description:
          pageError instanceof Error
            ? pageError.message
            : titleForLocale(
                locale,
                "无法读取计划任务",
                "Unable to read scheduled tasks",
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
      <SettingsSection
        title={titleForLocale(locale, "计划任务", "Scheduled Tasks")}
        actions={
          <Button
            variant="outline"
            size="sm"
            type="button"
            aria-label={t.refresh}
            onClick={() => void refresh()}
            disabled={tasksQuery.isFetching || settingsQuery.isFetching}
          >
            <RotateCcw className="size-3.5" />
            {t.refresh}
          </Button>
        }
      >
        <div className="space-y-3">
          <SelectionActionBar
            locale={locale}
            count={selectedTasks.length}
            onClear={selection.clear}
          >
            <Button
              type="button"
              size="xs"
              variant="outline"
              disabled={bulkBusy}
              onClick={() => void bulkSetEnabled(true)}
            >
              {titleForLocale(locale, "启用", "Enable")}
            </Button>
            <Button
              type="button"
              size="xs"
              variant="outline"
              disabled={bulkBusy}
              onClick={() => void bulkSetEnabled(false)}
            >
              {titleForLocale(locale, "停用", "Disable")}
            </Button>
            <Button
              type="button"
              size="xs"
              variant="default"
              disabled={bulkBusy}
              onClick={() => void bulkRun()}
            >
              <Play className="size-3" />
              {titleForLocale(locale, "运行选中任务", "Run selected")}
            </Button>
          </SelectionActionBar>
          <CronjobsTable
            locale={locale}
            tasks={tasks}
            isFetching={tasksQuery.isFetching}
            tasksIsError={tasksQuery.isError}
            timeZone={timeZone}
            selected={selection.selected}
            bulkBusy={bulkBusy}
            togglingTaskId={
              updateTask.isPending && !editingTask
                ? updateTask.variables?.task.id
                : undefined
            }
            runningTaskId={
              runTask.isPending ? runTask.variables?.id : undefined
            }
            onSelectAll={(checked) => selection.toggleRows(tasks, checked)}
            onSelectOne={selection.toggleId}
            onEdit={setEditingTask}
            onRun={(task) => runTask.mutate(task)}
            onToggleEnabled={(task, enabled) =>
              updateTask.mutate({
                task,
                payload: schedulePayload(task, enabled),
              })
            }
          />
        </div>
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
