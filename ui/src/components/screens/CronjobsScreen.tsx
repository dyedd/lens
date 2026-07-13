"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import {
  apiRequest,
  getApiErrorMessage,
  type CronjobItem,
  type CronjobRunResult,
  type SettingItem,
} from "@/lib/api";
import { titleForLocale, useI18n } from "@/lib/I18nContext";

import { CronjobsTable } from "./cronjobs/CronjobsTable";
import {
  intervalHours,
  parseRetentionSettings,
  RELAY_LOG_KEEP_ENABLED,
  RELAY_LOG_KEEP_PERIOD,
  REQUEST_LOG_PRUNE_TASK_ID,
  runAtTime,
  taskDraft,
  type RetentionDraft,
  type TaskDraft,
} from "./cronjobs/cronjobDrafts";

/** Render cron job schedules and manual run controls. */
export function CronjobsScreen() {
  const queryClient = useQueryClient();
  const { locale, t } = useI18n();
  const timeZone = useAppTimeZone();
  const [drafts, setDrafts] = useState<Record<string, TaskDraft>>({});
  const [retentionOverride, setRetentionOverride] =
    useState<RetentionDraft | null>(null);
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
  const retentionDraft =
    retentionOverride ?? parseRetentionSettings(settingsQuery.data);

  const updateTask = useMutation({
    mutationFn: async (task: CronjobItem) => {
      const draft = drafts[task.id] ?? taskDraft(task);
      const updatedTask = await apiRequest<CronjobItem>(
        `/admin/cronjobs/${encodeURIComponent(task.id)}`,
        {
          method: "PUT",
          body: JSON.stringify({
            enabled: draft.enabled,
            schedule_type: draft.scheduleType,
            interval_hours: intervalHours(draft),
            run_at_time:
              draft.scheduleType === "interval" ? null : runAtTime(draft),
            weekdays:
              draft.scheduleType === "weekly" ? draft.weekdays.map(Number) : [],
          }),
        },
      );
      if (task.id !== REQUEST_LOG_PRUNE_TASK_ID)
        return { task: updatedTask, settings: undefined };
      const settings = await apiRequest<SettingItem[]>("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({
          items: [
            {
              key: RELAY_LOG_KEEP_ENABLED,
              value: retentionDraft.enabled ? "true" : "false",
            },
            {
              key: RELAY_LOG_KEEP_PERIOD,
              value: retentionDraft.period.trim() || "7",
            },
          ],
        }),
      });
      return { task: updatedTask, settings };
    },
    onSuccess: (result, task) => {
      queryClient.setQueryData<CronjobItem[]>(["cronjobs"], (current) =>
        (current ?? []).map((item) =>
          item.id === result.task.id ? result.task : item,
        ),
      );
      if (result.settings) {
        queryClient.setQueryData(["settings"], result.settings);
        setRetentionOverride(null);
      }
      setDrafts((current) => {
        const next = { ...current };
        delete next[task.id];
        return next;
      });
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

  function setDraftValue(task: CronjobItem, value: Partial<TaskDraft>) {
    const currentDraft = drafts[task.id] ?? taskDraft(task);
    setDrafts((current) => ({
      ...current,
      [task.id]: { ...currentDraft, ...value },
    }));
  }

  function setRetentionValue(value: Partial<RetentionDraft>) {
    setRetentionOverride((current) => ({
      ...(current ?? retentionDraft),
      ...value,
    }));
  }

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
      <section className="flex min-w-0 flex-col gap-4">
        <div className="flex min-w-0 flex-col gap-6">
          <CronjobsTable
            drafts={drafts}
            isFetching={tasksQuery.isFetching}
            locale={locale}
            retentionDraft={retentionDraft}
            runningTaskId={
              runTask.isPending ? runTask.variables?.id : undefined
            }
            savingTaskId={
              updateTask.isPending ? updateTask.variables?.id : undefined
            }
            settings={settingsQuery.data}
            tasks={tasks}
            tasksIsError={tasksQuery.isError}
            timeZone={timeZone}
            onDraftChange={setDraftValue}
            onRetentionChange={setRetentionValue}
            onRun={(task) => runTask.mutate(task)}
            onSave={(task) => updateTask.mutate(task)}
          />
        </div>
      </section>
    </>
  );
}
