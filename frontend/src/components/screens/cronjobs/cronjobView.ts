import type { CronjobItem } from "@/lib/api/cronjobs";
import type { Locale } from "@/lib/I18nContext";

import { formatScheduleSummary } from "./CronjobEditors";
import { taskDraft } from "./cronjobDrafts";
import { taskTitle } from "./taskLabels";

export function cronjobTitle(locale: Locale, task: CronjobItem) {
  return taskTitle(locale, task.id, task.name);
}

export function cronjobScheduleLabel(locale: Locale, task: CronjobItem) {
  return formatScheduleSummary(taskDraft(task), locale);
}
