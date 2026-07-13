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
export type CronjobUpdate = {
  enabled?: boolean | null;
  schedule_type?: CronjobScheduleType | null;
  interval_hours?: number | null;
  run_at_time?: string | null;
  weekdays?: number[] | null;
};
export type CronjobRunResult = { cronjob: CronjobItem };
