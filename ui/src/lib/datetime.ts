import type { Locale } from "@/lib/I18nContext";

/** Formats a log timestamp for the selected locale and time zone. */
export function formatLogDateTime(
  value: string,
  locale: Locale,
  timeZone?: string,
) {
  return new Date(value).toLocaleString(
    locale === "zh-CN" ? "zh-CN" : "en-US",
    {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      ...(timeZone ? { timeZone } : {}),
    },
  );
}

/** Builds the current YYYYMMDD date bucket in the selected time zone. */
export function getDateBucketPrefix(timeZone?: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(timeZone ? { timeZone } : {}),
  }).formatToParts(new Date());
  const value = (type: string) =>
    parts.find((part) => part.type === type)?.value ?? "";
  return `${value("year")}${value("month")}${value("day")}`;
}
