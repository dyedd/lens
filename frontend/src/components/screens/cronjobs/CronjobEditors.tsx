import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { cn } from "@/lib/classNames";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import {
  type RetentionDraft,
  sortedWeekdays,
  type TaskDraft,
} from "./cronjobDrafts";

const WEEKDAYS = [
  { value: "1", zh: "一", en: "Mon" },
  { value: "2", zh: "二", en: "Tue" },
  { value: "3", zh: "三", en: "Wed" },
  { value: "4", zh: "四", en: "Thu" },
  { value: "5", zh: "五", en: "Fri" },
  { value: "6", zh: "六", en: "Sat" },
  { value: "7", zh: "日", en: "Sun" },
];

/** Format a compact schedule summary for collapsed task rows. */
export function formatScheduleSummary(draft: TaskDraft, locale: Locale) {
  if (draft.scheduleType === "interval") {
    return titleForLocale(
      locale,
      `每 ${draft.intervalHours} 小时`,
      `Every ${draft.intervalHours} hours`,
    );
  }
  const time = `${draft.runAtHour}:${draft.runAtMinute}`;
  if (draft.scheduleType === "daily") {
    return titleForLocale(locale, `每天 ${time}`, `Daily ${time}`);
  }
  const days = WEEKDAYS.filter((item) => draft.weekdays.includes(item.value))
    .map((item) => titleForLocale(locale, item.zh, item.en))
    .join(locale === "zh-CN" ? "、" : ", ");
  return titleForLocale(
    locale,
    `每周 ${days || "-"} ${time}`,
    `Weekly ${days || "-"} ${time}`,
  );
}

/** Render editable schedule controls for a cron job. */
export function ScheduleEditor({
  draft,
  locale,
  invalid,
  onChange,
}: {
  draft: TaskDraft;
  locale: Locale;
  invalid: boolean;
  onChange: (value: Partial<TaskDraft>) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <Select
        value={draft.scheduleType}
        onValueChange={(value) =>
          onChange({ scheduleType: value as TaskDraft["scheduleType"] })
        }
      >
        <SelectTrigger
          className="h-8 w-[5.5rem]"
          aria-label={titleForLocale(locale, "计划类型", "Schedule type")}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="interval">
            {titleForLocale(locale, "小时", "Hourly")}
          </SelectItem>
          <SelectItem value="daily">
            {titleForLocale(locale, "每天", "Daily")}
          </SelectItem>
          <SelectItem value="weekly">
            {titleForLocale(locale, "每周", "Weekly")}
          </SelectItem>
        </SelectContent>
      </Select>
      {draft.scheduleType === "interval" ? (
        <>
          <span className="text-xs text-muted-foreground">
            {titleForLocale(locale, "每", "Every")}
          </span>
          <Input
            className="h-8 w-16"
            type="number"
            min="1"
            step="1"
            value={draft.intervalHours}
            aria-invalid={invalid}
            onChange={(event) =>
              onChange({ intervalHours: event.target.value })
            }
          />
          <span className="text-xs text-muted-foreground">
            {titleForLocale(locale, "小时", "hours")}
          </span>
        </>
      ) : null}
      {draft.scheduleType === "weekly" ? (
        <div className="flex items-center gap-0.5">
          {WEEKDAYS.map((weekday) => {
            const selected = draft.weekdays.includes(weekday.value);
            return (
              <button
                key={weekday.value}
                type="button"
                className={cn(
                  "size-7 rounded-md text-[11px] transition-colors",
                  selected
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
                aria-pressed={selected}
                onClick={() => {
                  const next = selected
                    ? draft.weekdays.filter((item) => item !== weekday.value)
                    : [...draft.weekdays, weekday.value];
                  onChange({ weekdays: sortedWeekdays(next) });
                }}
              >
                {titleForLocale(locale, weekday.zh, weekday.en)}
              </button>
            );
          })}
        </div>
      ) : null}
      {draft.scheduleType === "daily" || draft.scheduleType === "weekly" ? (
        <TimeSelector
          locale={locale}
          hour={draft.runAtHour}
          minute={draft.runAtMinute}
          invalid={invalid}
          onChange={onChange}
        />
      ) : null}
    </div>
  );
}

function TimeSelector({
  locale,
  hour,
  minute,
  invalid,
  onChange,
}: {
  locale: Locale;
  hour: string;
  minute: string;
  invalid: boolean;
  onChange: (
    value: Partial<Pick<TaskDraft, "runAtHour" | "runAtMinute">>,
  ) => void;
}) {
  const hours = Array.from({ length: 24 }, (_, index) =>
    String(index).padStart(2, "0"),
  );
  const minutes = Array.from({ length: 12 }, (_, index) =>
    String(index * 5).padStart(2, "0"),
  );
  return (
    <div className="flex items-center gap-1.5">
      <Select
        value={hour}
        onValueChange={(value) => onChange({ runAtHour: value })}
      >
        <SelectTrigger
          className="h-8 w-16"
          aria-invalid={invalid}
          aria-label={titleForLocale(locale, "小时", "Hour")}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {hours.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <span className="text-xs text-muted-foreground">:</span>
      <Select
        value={minute}
        onValueChange={(value) => onChange({ runAtMinute: value })}
      >
        <SelectTrigger
          className="h-8 w-16"
          aria-invalid={invalid}
          aria-label={titleForLocale(locale, "分钟", "Minute")}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {minutes.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}

export type { RetentionDraft };
