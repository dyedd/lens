import { useState } from "react";

import {
  SettingsFieldList,
  SettingsFieldRow,
} from "@/components/settings/settingsLayout";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import type { CronjobItem } from "@/lib/api/cronjobs";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import { ScheduleEditor } from "./CronjobEditors";
import {
  isDraftInvalid,
  isRetentionDraftInvalid,
  REQUEST_LOG_PRUNE_TASK_ID,
  type RetentionDraft,
  type TaskDraft,
  taskDraft,
} from "./cronjobDrafts";
import { cronjobDescription, cronjobTitle } from "./cronjobView";

export function CronjobEditDialog({
  locale,
  task,
  retention,
  saving,
  onClose,
  onSave,
}: {
  locale: Locale;
  task: CronjobItem;
  retention: RetentionDraft;
  saving: boolean;
  onClose: () => void;
  onSave: (
    task: CronjobItem,
    draft: TaskDraft,
    retention: RetentionDraft,
  ) => void;
}) {
  const [draft, setDraft] = useState(() => taskDraft(task));
  const [retentionDraft, setRetentionDraft] = useState(retention);
  const isRetentionTask = task.id === REQUEST_LOG_PRUNE_TASK_ID;
  const invalidDraft = isDraftInvalid(draft);
  const invalidRetention =
    isRetentionTask && isRetentionDraftInvalid(retentionDraft);

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <AppDialogContent
        className="sm:max-w-lg"
        title={cronjobTitle(locale, task)}
        description={cronjobDescription(locale, task)}
        footer={
          <>
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              {titleForLocale(locale, "取消", "Cancel")}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={saving || invalidDraft || invalidRetention}
              onClick={() => onSave(task, draft, retentionDraft)}
            >
              {saving
                ? titleForLocale(locale, "保存中...", "Saving...")
                : titleForLocale(locale, "保存", "Save")}
            </Button>
          </>
        }
      >
        <SettingsFieldList>
          <Field data-invalid={invalidDraft}>
            <FieldLabel>
              {titleForLocale(locale, "计划", "Schedule")}
            </FieldLabel>
            <ScheduleEditor
              draft={draft}
              locale={locale}
              invalid={invalidDraft}
              onChange={(value) =>
                setDraft((current) => ({ ...current, ...value }))
              }
            />
          </Field>
          {isRetentionTask ? (
            <>
              <SettingsFieldRow
                title={titleForLocale(locale, "保留日志", "Keep logs")}
              >
                <Switch
                  checked={retentionDraft.enabled}
                  onCheckedChange={(checked) =>
                    setRetentionDraft((current) => ({
                      ...current,
                      enabled: checked,
                    }))
                  }
                />
              </SettingsFieldRow>
              <SettingsFieldRow
                title={titleForLocale(locale, "保留天数", "Retention days")}
                invalid={invalidRetention}
              >
                <Input
                  className="w-full"
                  type="number"
                  min="1"
                  max="36500"
                  step="1"
                  value={retentionDraft.period}
                  aria-invalid={invalidRetention}
                  disabled={!retentionDraft.enabled}
                  onChange={(event) =>
                    setRetentionDraft((current) => ({
                      ...current,
                      period: event.target.value,
                    }))
                  }
                />
              </SettingsFieldRow>
            </>
          ) : null}
        </SettingsFieldList>
      </AppDialogContent>
    </Dialog>
  );
}
