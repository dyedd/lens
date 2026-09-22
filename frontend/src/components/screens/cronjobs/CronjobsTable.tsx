import { Check, Pencil, Play, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { CronjobItem } from "@/lib/api/cronjobs";
import { formatLogDateTime } from "@/lib/datetime";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import {
  cronjobDescription,
  cronjobScheduleLabel,
  cronjobTitle,
} from "./cronjobView";

type CronjobsTableProps = {
  locale: Locale;
  tasks: CronjobItem[];
  isFetching: boolean;
  tasksIsError: boolean;
  timeZone: string;
  selected: Set<string>;
  bulkBusy: boolean;
  togglingTaskId?: string;
  runningTaskId?: string;
  onSelectAll: (checked: boolean) => void;
  onSelectOne: (taskId: string, checked: boolean) => void;
  onEdit: (task: CronjobItem) => void;
  onRun: (task: CronjobItem) => void;
  onToggleEnabled: (task: CronjobItem, enabled: boolean) => void;
};

function formatTaskTime(
  locale: Locale,
  value: string | null | undefined,
  timeZone: string,
) {
  return value
    ? formatLogDateTime(value, locale, timeZone)
    : titleForLocale(locale, "未执行", "Never");
}

/** Render cron jobs as a compact table with enable/run actions. */
export function CronjobsTable({
  locale,
  tasks,
  isFetching,
  tasksIsError,
  timeZone,
  selected,
  bulkBusy,
  togglingTaskId,
  runningTaskId,
  onSelectAll,
  onSelectOne,
  onEdit,
  onRun,
  onToggleEnabled,
}: CronjobsTableProps) {
  if (tasksIsError) return null;
  const allSelected =
    tasks.length > 0 && tasks.every((task) => selected.has(task.id));
  const someSelected = tasks.some((task) => selected.has(task.id));

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-[44px] text-center">
            <div className="flex h-7 items-center justify-center">
              <Checkbox
                checked={
                  allSelected ? true : someSelected ? "indeterminate" : false
                }
                disabled={bulkBusy}
                onCheckedChange={(checked) => onSelectAll(checked === true)}
                aria-label={titleForLocale(
                  locale,
                  "全选定时任务",
                  "Select all cron jobs",
                )}
              />
            </div>
          </TableHead>
          <TableHead>{titleForLocale(locale, "任务", "Task")}</TableHead>
          <TableHead>{titleForLocale(locale, "计划", "Schedule")}</TableHead>
          <TableHead className="w-[72px]">
            {titleForLocale(locale, "状态", "Status")}
          </TableHead>
          <TableHead>
            {titleForLocale(locale, "下次执行", "Next run")}
          </TableHead>
          <TableHead className="w-[52px] text-right">
            {titleForLocale(locale, "操作", "Actions")}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tasks.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={6}
              className="h-32 text-center text-muted-foreground"
            >
              {isFetching
                ? titleForLocale(locale, "加载中...", "Loading...")
                : titleForLocale(locale, "暂无定时任务", "No cron jobs")}
            </TableCell>
          </TableRow>
        ) : (
          tasks.map((task) => {
            const busy =
              bulkBusy ||
              task.status === "running" ||
              togglingTaskId === task.id ||
              runningTaskId === task.id;
            return (
              <TableRow
                key={task.id}
                data-state={selected.has(task.id) ? "selected" : undefined}
              >
                <TableCell className="w-[44px] py-1.5 text-center">
                  <div className="flex h-7 items-center justify-center">
                    <Checkbox
                      checked={selected.has(task.id)}
                      disabled={bulkBusy}
                      onCheckedChange={(checked) =>
                        onSelectOne(task.id, checked === true)
                      }
                      aria-label={titleForLocale(
                        locale,
                        `选择 ${cronjobTitle(locale, task)}`,
                        `Select ${cronjobTitle(locale, task)}`,
                      )}
                    />
                  </div>
                </TableCell>
                <TableCell className="max-w-[18rem]">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-foreground">
                      {cronjobTitle(locale, task)}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {cronjobDescription(locale, task)}
                    </p>
                  </div>
                </TableCell>
                <TableCell>
                  <button
                    type="button"
                    className="inline-flex max-w-[14rem] items-center gap-1.5 text-left text-xs text-foreground hover:text-foreground/80"
                    onClick={() => onEdit(task)}
                  >
                    <span className="truncate">
                      {cronjobScheduleLabel(locale, task)}
                    </span>
                    <Pencil className="size-3 shrink-0 text-muted-foreground" />
                  </button>
                </TableCell>
                <TableCell>
                  <Switch
                    checked={task.enabled}
                    disabled={busy}
                    onCheckedChange={(checked) =>
                      onToggleEnabled(task, checked)
                    }
                    aria-label={titleForLocale(
                      locale,
                      task.enabled ? "停用任务" : "启用任务",
                      task.enabled ? "Disable task" : "Enable task",
                    )}
                  />
                </TableCell>
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                  <span
                    className="inline-flex items-center gap-1"
                    title={task.last_error ?? undefined}
                  >
                    {task.status === "succeeded" ? (
                      <Check className="size-3.5 shrink-0" />
                    ) : null}
                    {task.status === "failed" ? (
                      <X className="size-3.5 shrink-0" />
                    ) : null}
                    {formatTaskTime(locale, task.next_run_at, timeZone)}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        aria-label={titleForLocale(
                          locale,
                          "执行任务",
                          "Run task",
                        )}
                        disabled={busy}
                        onClick={() => onRun(task)}
                      >
                        <Play />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {titleForLocale(locale, "执行任务", "Run task")}
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
