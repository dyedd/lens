import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Switch } from "@/components/ui/Switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/ToggleGroup";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import {
  sortedWeekdays,
  type RetentionDraft,
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

function scheduleTypeOptions(locale: Locale) {
  return [
    {
      value: "interval" as const,
      label: titleForLocale(locale, "小时", "Hourly"),
    },
    { value: "daily" as const, label: titleForLocale(locale, "每天", "Daily") },
    {
      value: "weekly" as const,
      label: titleForLocale(locale, "每周", "Weekly"),
    },
  ];
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
    <div className="mx-auto flex min-w-72 max-w-72 flex-col items-center gap-2">
      <SegmentedControl
        className="self-center"
        value={draft.scheduleType}
        onValueChange={(value) => onChange({ scheduleType: value })}
        options={scheduleTypeOptions(locale)}
      />
      {draft.scheduleType === "interval" ? (
        <div className="flex items-center justify-center gap-2">
          <span className="text-sm text-muted-foreground">
            {titleForLocale(locale, "每", "Every")}
          </span>
          <Input
            className="w-20"
            type="number"
            min="1"
            step="1"
            value={draft.intervalHours}
            aria-invalid={invalid}
            onChange={(event) =>
              onChange({ intervalHours: event.target.value })
            }
          />
          <span className="text-sm text-muted-foreground">
            {titleForLocale(locale, "小时", "hours")}
          </span>
        </div>
      ) : null}
      {draft.scheduleType === "daily" ? (
        <TimeSelector
          locale={locale}
          hour={draft.runAtHour}
          minute={draft.runAtMinute}
          invalid={invalid}
          onChange={onChange}
        />
      ) : null}
      {draft.scheduleType === "weekly" ? (
        <div className="flex flex-col items-center gap-2">
          <ToggleGroup
            type="multiple"
            variant="outline"
            size="sm"
            value={draft.weekdays}
            onValueChange={(value) =>
              onChange({ weekdays: sortedWeekdays(value) })
            }
            aria-label={titleForLocale(locale, "执行星期", "Run weekdays")}
          >
            {WEEKDAYS.map((weekday) => (
              <ToggleGroupItem key={weekday.value} value={weekday.value}>
                {titleForLocale(locale, weekday.zh, weekday.en)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <TimeSelector
            locale={locale}
            hour={draft.runAtHour}
            minute={draft.runAtMinute}
            invalid={invalid}
            onChange={onChange}
          />
        </div>
      ) : null}
    </div>
  );
}

/** Render request-log retention controls. */
export function RetentionEditor({
  draft,
  locale,
  invalid,
  disabled,
  onChange,
}: {
  draft: RetentionDraft;
  locale: Locale;
  invalid: boolean;
  disabled: boolean;
  onChange: (value: Partial<RetentionDraft>) => void;
}) {
  return (
    <div className="mx-auto flex min-w-52 max-w-52 flex-col items-center gap-2">
      <div className="flex items-center justify-center gap-2">
        <Switch
          checked={draft.enabled}
          disabled={disabled}
          onCheckedChange={(checked) => onChange({ enabled: checked })}
          aria-label={titleForLocale(locale, "保留日志", "Keep logs")}
        />
        <span className="text-sm text-muted-foreground">
          {titleForLocale(locale, "保留日志", "Keep logs")}
        </span>
      </div>
      <div className="flex items-center justify-center gap-2">
        <span className="text-sm text-muted-foreground">
          {titleForLocale(locale, "保留", "Keep")}
        </span>
        <Input
          className="w-20"
          type="number"
          min="1"
          step="1"
          value={draft.period}
          aria-invalid={invalid}
          disabled={disabled || !draft.enabled}
          onChange={(event) => onChange({ period: event.target.value })}
        />
        <span className="text-sm text-muted-foreground">
          {titleForLocale(locale, "天", "days")}
        </span>
      </div>
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
    <div className="flex items-center gap-2">
      <Select
        value={hour}
        onValueChange={(value) => onChange({ runAtHour: value })}
      >
        <SelectTrigger
          className="w-16"
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
      <span className="text-sm text-muted-foreground">:</span>
      <Select
        value={minute}
        onValueChange={(value) => onChange({ runAtMinute: value })}
      >
        <SelectTrigger
          className="w-16"
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
