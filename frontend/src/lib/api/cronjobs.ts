export type CronjobStatus =
  | "idle"
  | "running"
  | "succeeded"
  | "failed"
  | "disabled";
export type CronjobScheduleType = "interval" | "daily" | "weekly";
export type CronjobItem = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  schedule_type: CronjobScheduleType;
  interval_hours: number;
  run_at_time?: string | null;
  weekdays: number[];
  status: CronjobStatus;
  last_started_at?: string | null;
  last_finished_at?: string | null;
  last_error?: string | null;
  next_run_at?: string | null;
};
type CronjobUpdate = Pick<
  CronjobItem,
  "enabled" | "schedule_type" | "interval_hours" | "run_at_time" | "weekdays"
>;

function isCronjobItem(value: unknown): value is CronjobItem {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.description === "string" &&
    typeof value.enabled === "boolean" &&
    (value.schedule_type === "interval" ||
      value.schedule_type === "daily" ||
      value.schedule_type === "weekly") &&
    Number.isFinite(value.interval_hours) &&
    Number(value.interval_hours) >= 1 &&
    Array.isArray(value.weekdays) &&
    value.weekdays.every(
      (day) => Number.isInteger(day) && Number(day) >= 1 && Number(day) <= 7,
    ) &&
    (value.status === "idle" ||
      value.status === "running" ||
      value.status === "succeeded" ||
      value.status === "failed" ||
      value.status === "disabled") &&
    [
      value.run_at_time,
      value.last_started_at,
      value.last_finished_at,
      value.last_error,
      value.next_run_at,
    ].every((field) => field == null || typeof field === "string")
  );
}

export async function requestCronjobs(): Promise<CronjobItem[]> {
  const value = await apiRequest<unknown>("/admin/cronjobs");
  if (!Array.isArray(value) || !value.every(isCronjobItem)) {
    throw new ApiError("Invalid scheduled tasks response from API", 200);
  }
  return value;
}

export async function updateCronjob(
  id: string,
  payload: CronjobUpdate,
): Promise<CronjobItem> {
  const value = await apiRequest<unknown>(
    `/admin/cronjobs/${encodeURIComponent(id)}`,
    { method: "PUT", body: JSON.stringify(payload) },
  );
  if (!isCronjobItem(value)) {
    throw new ApiError("Invalid scheduled task update response from API", 200);
  }
  return value;
}

export async function runCronjob(id: string): Promise<CronjobItem> {
  const value = await apiRequest<unknown>(
    `/admin/cronjobs/${encodeURIComponent(id)}/runs`,
    { method: "POST" },
  );
  if (!isRecord(value) || !isCronjobItem(value.cronjob)) {
    throw new ApiError("Invalid scheduled task run response from API", 200);
  }
  return value.cronjob;
}

import { ApiError, apiRequest, isRecord } from "./client";
