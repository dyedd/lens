import type {
  GatewayApiKey,
  GatewayApiKeyPayload,
  ModelGroup,
  ProtocolKind,
} from "@/lib/api";
import { PROTOCOL_LABELS } from "@/lib/protocols";
import { titleForLocale, type Locale } from "@/lib/I18nContext";
import { formatExpiresAt, parseGatewayExpiresAt } from "./gatewayDateTime";

export {
  formatDateLabel,
  formatDateOnly,
  formatDateTime,
  formatExpiresAt,
  getTimeInZone,
  getTimeZoneDateParts,
  getTimeZoneOffsetMs,
  parseGatewayExpiresAt,
} from "./gatewayDateTime";

export type GatewayApiKeyForm = {
  remark: string;
  enabled: boolean;
  isModelRestrictionEnabled: boolean;
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
  isModelRestrictionEnabled: false,
  allowedModels: [],
  maxCostUsd: "0",
  expiresOn: undefined,
};

/** Masks a gateway API key while preserving recognizable edge characters. */
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

/** Converts a gateway API key into editable form state. */
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
    isModelRestrictionEnabled: item.allowed_models.length > 0,
    allowedModels: [...item.allowed_models],
    maxCostUsd: String(item.max_cost_usd),
    expiresOn: expires.expiresOn,
  };
}

/** Converts gateway API key form state into an API payload. */
export function toGatewayApiKeyPayload(
  form: GatewayApiKeyForm,
  timeZone: string,
): GatewayApiKeyPayload {
  return {
    remark: form.remark.trim(),
    enabled: form.enabled,
    allowed_models: form.isModelRestrictionEnabled ? form.allowedModels : [],
    max_cost_usd: Math.max(Number(form.maxCostUsd || "0") || 0, 0),
    expires_at: formatExpiresAt(form.expiresOn, timeZone),
  };
}

/** Formats a gateway monetary amount for the selected locale. */
export function formatGatewayAmount(locale: Locale, value: number) {
  return new Intl.NumberFormat(locale === "zh-CN" ? "zh-CN" : "en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  }).format(value);
}

/** Formats gateway API key spending against its configured limit. */
export function formatGatewayLimit(locale: Locale, item: GatewayApiKey) {
  if (item.max_cost_usd > 0) {
    return `${formatGatewayAmount(locale, item.spent_cost_usd)} / ${formatGatewayAmount(locale, item.max_cost_usd)} USD`;
  }
  return titleForLocale(locale, "不限额", "Unlimited");
}

/** Reports whether a gateway API key has expired. */
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

/** Reports whether a gateway API key has exhausted its cost limit. */
export function isGatewayKeyOutOfBalance(item: GatewayApiKey) {
  return item.max_cost_usd > 0 && item.spent_cost_usd >= item.max_cost_usd;
}

/** Builds selectable gateway model-group options from enabled groups. */
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

/** Formats a localized summary of supported protocols. */
export function protocolSummary(locale: Locale, protocols: ProtocolKind[]) {
  return protocols
    .map((protocol) => {
      const labels = PROTOCOL_LABELS[protocol];
      return locale === "zh-CN" ? labels.zh : labels.en;
    })
    .join(" / ");
}
