import { format } from "date-fns";
import { enUS, zhCN } from "date-fns/locale";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

/** Return calendar date parts for a timestamp in the selected time zone. */
export function getTimeZoneDateParts(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const value = (type: string) =>
    parts.find((part) => part.type === type)?.value ?? "";
  return {
    year: Number(value("year")),
    month: Number(value("month")),
    day: Number(value("day")),
  };
}

/** Calculate the UTC offset for a timestamp in the selected time zone. */
export function getTimeZoneOffsetMs(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const value = (type: string) =>
    parts.find((part) => part.type === type)?.value ?? "0";
  const asUtc = Date.UTC(
    Number(value("year")),
    Number(value("month")) - 1,
    Number(value("day")),
    Number(value("hour")),
    Number(value("minute")),
    Number(value("second")),
  );
  return asUtc - date.getTime();
}

/** Create a timestamp for local date-time fields in the selected time zone. */
export function getTimeInZone(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  second: number,
  millisecond: number,
  timeZone: string,
) {
  const utcGuess = new Date(
    Date.UTC(year, month, day, hour, minute, second, millisecond),
  );
  const offset = getTimeZoneOffsetMs(utcGuess, timeZone);
  return new Date(utcGuess.getTime() - offset);
}

/** Parse an API expiry timestamp into date-picker state. */
export function parseGatewayExpiresAt(
  value: string | null | undefined,
  timeZone: string,
) {
  if (!value) {
    return { expiresOn: undefined };
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { expiresOn: undefined };
  }
  const parts = getTimeZoneDateParts(date, timeZone);
  if (!parts.year || !parts.month || !parts.day) {
    return { expiresOn: undefined };
  }
  return {
    expiresOn: new Date(parts.year, parts.month - 1, parts.day),
  };
}

/** Format a date-picker expiry as the final instant of that local day. */
export function formatExpiresAt(date: Date | undefined, timeZone: string) {
  if (!date) {
    return null;
  }
  const nextDate = getTimeInZone(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
    23,
    59,
    59,
    999,
    timeZone,
  );
  if (Number.isNaN(nextDate.getTime())) {
    return null;
  }
  return nextDate.toISOString();
}

/** Format an optional timestamp for the selected locale and time zone. */
export function formatDateTime(
  locale: Locale,
  value: string | null | undefined,
  timeZone: string,
) {
  if (!value) {
    return titleForLocale(locale, "未设置", "Not set");
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(locale === "zh-CN" ? "zh-CN" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  });
}

/** Format an optional date for the selected locale and time zone. */
export function formatDateOnly(
  locale: Locale,
  value: string | null | undefined,
  timeZone: string,
) {
  if (!value) {
    return titleForLocale(locale, "未设置", "Not set");
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString(locale === "zh-CN" ? "zh-CN" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone,
  });
}

/** Format a date-picker value for the selected locale. */
export function formatDateLabel(locale: Locale, value?: Date) {
  if (!value) {
    return titleForLocale(locale, "选择日期", "Pick a date");
  }
  return format(value, locale === "zh-CN" ? "PPP" : "PP", {
    locale: locale === "zh-CN" ? zhCN : enUS,
  });
}
