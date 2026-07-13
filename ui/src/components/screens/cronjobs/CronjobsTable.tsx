import { Play, Save } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import type { CronjobItem, SettingItem } from "@/lib/api";
import { formatLogDateTime } from "@/lib/datetime";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { RetentionEditor, ScheduleEditor } from "./CronjobEditors";
import {
  isDraftChanged,
  isDraftInvalid,
  isRetentionDraftChanged,
  isRetentionDraftInvalid,
  REQUEST_LOG_PRUNE_TASK_ID,
  REQUEST_LOG_STATS_PERSIST_TASK_ID,
  taskDraft,
  type RetentionDraft,
  type TaskDraft,
} from "./cronjobDrafts";

function statusLabel(locale: Locale, status: CronjobItem["status"]) {
  const labels: Record<CronjobItem["status"], [string, string]> = {
    idle: ["空闲", "Idle"],
    running: ["运行中", "Running"],
    succeeded: ["成功", "Succeeded"],
    failed: ["失败", "Failed"],
    disabled: ["已停用", "Disabled"],
  };
  const [zh, en] = labels[status];
  return titleForLocale(locale, zh, en);
}

function statusVariant(status: CronjobItem["status"]) {
  if (status === "failed") return "destructive" as const;
  if (status === "running" || status === "succeeded")
    return "secondary" as const;
  return "outline" as const;
}

function taskTitle(locale: Locale, task: CronjobItem) {
  const labels: Record<string, [string, string]> = {
    [REQUEST_LOG_PRUNE_TASK_ID]: ["请求日志清理", "Request log cleanup"],
    [REQUEST_LOG_STATS_PERSIST_TASK_ID]: [
      "请求日志统计落库",
      "Request log stats persist",
    ],
    model_price_sync: ["模型价格同步", "Model price sync"],
  };
  const label = labels[task.id];
  return label ? titleForLocale(locale, label[0], label[1]) : task.name;
}

function taskDescription(locale: Locale, task: CronjobItem) {
  const labels: Record<string, [string, string]> = {
    [REQUEST_LOG_PRUNE_TASK_ID]: [
      "按日志保留天数清理过期请求日志",
      "Prune request logs by the retention window",
    ],
    [REQUEST_LOG_STATS_PERSIST_TASK_ID]: [
      "归档请求日志统计数据",
      "Persist request log statistics",
    ],
    model_price_sync: [
      "从 models.dev 同步模型价格",
      "Sync model prices from models.dev",
    ],
  };
  const label = labels[task.id];
  return label ? titleForLocale(locale, label[0], label[1]) : task.description;
}

function formatTaskTime(
  locale: Locale,
  value: string | null | undefined,
  timeZone: string,
) {
  return value
    ? formatLogDateTime(value, locale, timeZone)
    : titleForLocale(locale, "未执行", "Never");
}

type CronjobsTableProps = {
  drafts: Record<string, TaskDraft>;
  isFetching: boolean;
  locale: Locale;
  retentionDraft: RetentionDraft;
  runningTaskId?: string;
  savingTaskId?: string;
  settings: SettingItem[] | undefined;
  tasks: CronjobItem[];
  tasksIsError: boolean;
  timeZone: string;
  onDraftChange: (task: CronjobItem, value: Partial<TaskDraft>) => void;
  onRetentionChange: (value: Partial<RetentionDraft>) => void;
  onRun: (task: CronjobItem) => void;
  onSave: (task: CronjobItem) => void;
};

/** Render the cron job schedule table. */
export function CronjobsTable(props: CronjobsTableProps) {
  const {
    drafts,
    isFetching,
    locale,
    retentionDraft,
    runningTaskId,
    savingTaskId,
    settings,
    tasks,
    tasksIsError,
    timeZone,
    onDraftChange,
    onRetentionChange,
    onRun,
    onSave,
  } = props;
  return (
    <Card className="min-w-0 py-0">
      <CardContent className="min-w-0 p-3 sm:p-5">
        <Table className="min-w-[1320px] table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-64">
                {titleForLocale(locale, "任务", "Task")}
              </TableHead>
              <TableHead className="w-16">
                {titleForLocale(locale, "启用", "Enabled")}
              </TableHead>
              <TableHead className="w-72 text-center">
                {titleForLocale(locale, "计划", "Schedule")}
              </TableHead>
              <TableHead className="w-56 text-center">
                {titleForLocale(locale, "任务配置", "Task config")}
              </TableHead>
              <TableHead className="w-24">
                {titleForLocale(locale, "状态", "Status")}
              </TableHead>
              <TableHead className="w-36">
                {titleForLocale(locale, "上次执行", "Last run")}
              </TableHead>
              <TableHead className="w-36">
                {titleForLocale(locale, "下次执行", "Next run")}
              </TableHead>
              <TableHead className="w-40 text-right">
                {titleForLocale(locale, "操作", "Actions")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {!tasksIsError && tasks.length ? (
              tasks.map((task) => {
                const draft = drafts[task.id] ?? taskDraft(task);
                const invalidDraft = isDraftInvalid(draft);
                const isRetentionTask = task.id === REQUEST_LOG_PRUNE_TASK_ID;
                const isWaitingForSettings =
                  isRetentionTask && settings === undefined;
                const invalidRetention =
                  isRetentionTask && isRetentionDraftInvalid(retentionDraft);
                const retentionChanged =
                  isRetentionTask &&
                  isRetentionDraftChanged(settings, retentionDraft);
                const changed = isDraftChanged(task, draft) || retentionChanged;
                const running =
                  task.status === "running" || runningTaskId === task.id;
                return (
                  <TableRow key={task.id}>
                    <TableCell>
                      <div className="flex min-w-52 flex-col gap-1">
                        <span className="font-medium text-foreground">
                          {taskTitle(locale, task)}
                        </span>
                        <span className="max-w-80 truncate text-xs text-muted-foreground">
                          {taskDescription(locale, task)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Switch
                        checked={draft.enabled}
                        onCheckedChange={(checked) =>
                          onDraftChange(task, { enabled: checked })
                        }
                        aria-label={titleForLocale(
                          locale,
                          "启用任务",
                          "Enable task",
                        )}
                      />
                    </TableCell>
                    <TableCell className="text-center align-middle">
                      <ScheduleEditor
                        draft={draft}
                        locale={locale}
                        invalid={invalidDraft}
                        onChange={(value) => onDraftChange(task, value)}
                      />
                    </TableCell>
                    <TableCell className="text-center align-middle">
                      {isRetentionTask ? (
                        <RetentionEditor
                          draft={retentionDraft}
                          locale={locale}
                          invalid={invalidRetention}
                          disabled={isWaitingForSettings}
                          onChange={onRetentionChange}
                        />
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Badge variant={statusVariant(task.status)}>
                          {statusLabel(locale, task.status)}
                        </Badge>
                        {task.last_error ? (
                          <span
                            className="max-w-64 truncate text-xs text-muted-foreground"
                            title={task.last_error}
                          >
                            {task.last_error}
                          </span>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell>
                      {formatTaskTime(
                        locale,
                        task.last_finished_at ?? task.last_started_at,
                        timeZone,
                      )}
                    </TableCell>
                    <TableCell>
                      {formatTaskTime(locale, task.next_run_at, timeZone)}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={
                            !changed ||
                            isWaitingForSettings ||
                            invalidDraft ||
                            invalidRetention ||
                            savingTaskId === task.id
                          }
                          onClick={() => onSave(task)}
                        >
                          <Save data-icon="inline-start" />
                          {titleForLocale(locale, "保存", "Save")}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={running}
                          onClick={() => onRun(task)}
                        >
                          <Play data-icon="inline-start" />
                          {running
                            ? titleForLocale(locale, "运行中", "Running")
                            : titleForLocale(locale, "运行", "Run")}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            ) : tasksIsError ? null : (
              <TableRow>
                <TableCell
                  colSpan={8}
                  className="py-8 text-center text-muted-foreground"
                >
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
  );
}
