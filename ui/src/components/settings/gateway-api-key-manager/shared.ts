import { format } from "date-fns";
import { enUS, zhCN } from "date-fns/locale";
import type {
  GatewayApiKey,
  GatewayApiKeyPayload,
  ModelGroup,
  ProtocolKind,
} from "@/lib/api";
import { PROTOCOL_LABELS } from "@/lib/protocols";
import { titleForLocale, type Locale } from "@/lib/i18n";
export { titleForLocale };

export type GatewayApiKeyForm = {
  remark: string;
  enabled: boolean;
  restrictModels: boolean;
  allowedModels: string[];
  maxCostUsd: string;
  expiresOn?: Date;
};

export type GatewayModelGroupOption = {
  name: string;
  protocols: ProtocolKind[];
  enabledItemCount: number;
  channelNames: string[];
};

export const EMPTY_FORM: GatewayApiKeyForm = {
  remark: "",
  enabled: true,
  restrictModels: false,
  allowedModels: [],
  maxCostUsd: "0",
  expiresOn: undefined,
};

export function maskGatewayKey(value: string) {
  if (!value) {
    return "";
  }
  if (value.length <= 12) {
    return (
      value[0] + "*".repeat(Math.max(value.length - 2, 1)) + value.slice(-1)
    );
  }
  return (
    value.slice(0, 8) +
    "*".repeat(Math.max(value.length - 16, 8)) +
    value.slice(-8)
  );
}

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

export function toGatewayApiKeyForm(
  item: GatewayApiKey | undefined,
  timeZone: string,
): GatewayApiKeyForm {
  if (!item) {
    return { ...EMPTY_FORM };
  }
  const expires = parseGatewayExpiresAt(item.expires_at, timeZone);
  return {
    remark: item.remark,
    enabled: item.enabled,
    restrictModels: item.allowed_models.length > 0,
    allowedModels: [...item.allowed_models],
    maxCostUsd: String(item.max_cost_usd),
    expiresOn: expires.expiresOn,
  };
}

export function toGatewayApiKeyPayload(
  form: GatewayApiKeyForm,
  timeZone: string,
): GatewayApiKeyPayload {
  return {
    remark: form.remark.trim(),
    enabled: form.enabled,
    allowed_models: form.restrictModels ? form.allowedModels : [],
    max_cost_usd: Math.max(Number(form.maxCostUsd || "0") || 0, 0),
    expires_at: formatExpiresAt(form.expiresOn, timeZone),
  };
}

export function formatGatewayAmount(locale: Locale, value: number) {
  return new Intl.NumberFormat(locale === "zh-CN" ? "zh-CN" : "en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  }).format(value);
}

export function formatGatewayLimit(locale: Locale, item: GatewayApiKey) {
  if (item.max_cost_usd > 0) {
    return `${formatGatewayAmount(locale, item.spent_cost_usd)} / ${formatGatewayAmount(locale, item.max_cost_usd)} USD`;
  }
  return titleForLocale(locale, "不限额", "Unlimited");
}

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

export function formatDateLabel(locale: Locale, value?: Date) {
  if (!value) {
    return titleForLocale(locale, "选择日期", "Pick a date");
  }
  return format(value, locale === "zh-CN" ? "PPP" : "PP", {
    locale: locale === "zh-CN" ? zhCN : enUS,
  });
}

export function isGatewayKeyExpired(item: GatewayApiKey) {
  if (!item.expires_at) {
    return false;
  }
  const expiresAt = new Date(item.expires_at);
  if (Number.isNaN(expiresAt.getTime())) {
    return true;
  }
  return expiresAt.getTime() <= Date.now();
}

export function isGatewayKeyOutOfBalance(item: GatewayApiKey) {
  return item.max_cost_usd > 0 && item.spent_cost_usd >= item.max_cost_usd;
}

export function buildGatewayModelGroupOptions(groups: ModelGroup[]) {
  const mapping = new Map<string, GatewayModelGroupOption>();

  for (const group of groups) {
    if (group.route_group_id) {
      continue;
    }
    const enabledItems = group.items.filter((item) => item.enabled);
    if (enabledItems.length === 0) {
      continue;
    }
    const current =
      mapping.get(group.name) ??
      ({
        name: group.name,
        protocols: [],
        enabledItemCount: 0,
        channelNames: [],
      } satisfies GatewayModelGroupOption);

    for (const protocol of group.protocols) {
      if (!current.protocols.includes(protocol)) {
        current.protocols = [...current.protocols, protocol];
      }
    }
    current.enabledItemCount += enabledItems.length;
    current.channelNames = Array.from(
      new Set([
        ...current.channelNames,
        ...enabledItems.map((item) => item.channel_name).filter(Boolean),
      ]),
    );
    mapping.set(group.name, current);
  }

  return [...mapping.values()].sort((left, right) =>
    left.name.localeCompare(right.name),
  );
}

export function protocolSummary(locale: Locale, protocols: ProtocolKind[]) {
  return protocols
    .map((protocol) => {
      const labels = PROTOCOL_LABELS[protocol];
      return locale === "zh-CN" ? labels.zh : labels.en;
    })
    .join(" / ");
}
