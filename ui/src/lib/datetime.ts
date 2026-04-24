import type { Locale } from "@/lib/i18n"

export function formatLogDateTime(value: string, locale: Locale) {
  return new Date(value).toLocaleString(locale === "zh-CN" ? "zh-CN" : "en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
}
