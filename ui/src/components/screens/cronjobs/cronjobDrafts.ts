import type { CronjobItem, CronjobScheduleType, SettingItem } from "@/lib/api";

export type TaskDraft = {
  enabled: boolean;
  scheduleType: CronjobScheduleType;
  intervalHours: string;
  runAtHour: string;
  runAtMinute: string;
  weekdays: string[];
};

export type RetentionDraft = {
  enabled: boolean;
  period: string;
};

export const REQUEST_LOG_PRUNE_TASK_ID = "request_log_prune";
export const REQUEST_LOG_STATS_PERSIST_TASK_ID = "request_log_stats_persist";
export const RELAY_LOG_KEEP_ENABLED = "relay_log_keep_enabled";
export const RELAY_LOG_KEEP_PERIOD = "relay_log_keep_period";

/** Parse the interval hour value from a task draft. */
export function intervalHours(draft: TaskDraft) {
  return Number(draft.intervalHours);
}

/** Return unique weekdays in calendar order. */
export function sortedWeekdays(values: string[]) {
  return [...new Set(values)].sort(
    (left, right) => Number(left) - Number(right),
  );
}

function splitRunAtTime(value: string | null | undefined) {
  const [hour = "03", minute = "00"] = (value || "03:00").split(":", 2);
  return {
    runAtHour: hour.padStart(2, "0").slice(0, 2),
    runAtMinute: minute.padStart(2, "0").slice(0, 2),
  };
}

/** Build the API run-at time from a task draft. */
export function runAtTime(draft: TaskDraft) {
  return `${draft.runAtHour}:${draft.runAtMinute}`;
}

/** Create an editable draft from a cron job. */
export function taskDraft(item: CronjobItem): TaskDraft {
  const runAt = splitRunAtTime(item.run_at_time);
  return {
    enabled: item.enabled,
    scheduleType: item.schedule_type,
    intervalHours: String(Math.max(item.interval_hours, 1)),
    runAtHour: runAt.runAtHour,
    runAtMinute: runAt.runAtMinute,
    weekdays: sortedWeekdays(item.weekdays.map(String)),
  };
}

/** Read retention settings into an editable draft. */
export function parseRetentionSettings(
  items: SettingItem[] | undefined,
): RetentionDraft {
  const mapping = new Map((items ?? []).map((item) => [item.key, item.value]));
  return {
    enabled: !["0", "false", "no", "off"].includes(
      (mapping.get(RELAY_LOG_KEEP_ENABLED) ?? "true").toLowerCase(),
    ),
    period: mapping.get(RELAY_LOG_KEEP_PERIOD) ?? "7",
  };
}

function normalizeRetentionDraft(draft: RetentionDraft) {
  return { enabled: draft.enabled, period: Number(draft.period) };
}

/** Check whether retention settings have changed. */
export function isRetentionDraftChanged(
  settings: SettingItem[] | undefined,
  draft: RetentionDraft,
) {
  const current = normalizeRetentionDraft(parseRetentionSettings(settings));
  return (
    JSON.stringify(current) !== JSON.stringify(normalizeRetentionDraft(draft))
  );
}

/** Check whether enabled retention settings are invalid. */
export function isRetentionDraftInvalid(draft: RetentionDraft) {
  if (!draft.enabled) return false;
  const days = Number(draft.period);
  return !Number.isInteger(days) || days < 1;
}

function normalizeDraftForCompare(draft: TaskDraft) {
  return {
    enabled: draft.enabled,
    scheduleType: draft.scheduleType,
    intervalHours: intervalHours(draft),
    runAtTime: draft.scheduleType === "interval" ? null : runAtTime(draft),
    weekdays:
      draft.scheduleType === "weekly" ? sortedWeekdays(draft.weekdays) : [],
  };
}

/** Check whether a task schedule draft has changed. */
export function isDraftChanged(
  item: CronjobItem,
  draft: TaskDraft | undefined,
) {
  if (!draft) return false;
  return (
    JSON.stringify(normalizeDraftForCompare(taskDraft(item))) !==
    JSON.stringify(normalizeDraftForCompare(draft))
  );
}

/** Check whether a task schedule draft is invalid. */
export function isDraftInvalid(draft: TaskDraft) {
  const intervalNumber = Number(draft.intervalHours);
  if (!Number.isInteger(intervalNumber) || intervalNumber < 1) return true;
  if (
    draft.scheduleType !== "interval" &&
    (!draft.runAtHour || !draft.runAtMinute)
  ) {
    return true;
  }
  return draft.scheduleType === "weekly" && draft.weekdays.length === 0;
}
