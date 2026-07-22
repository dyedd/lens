import type {
  ProtocolKind,
  RouteSnapshot,
  SiteRuntimeSummary,
} from "@/lib/api";
import { compactProtocolLabel } from "@/lib/protocols";
import {
  credentialDisplayName,
  formatCooldownDuration,
  protocolConfigDisplayName,
  type Locale,
  type SiteRow,
} from "./channelShared";

export type ChannelHealthRow = RouteSnapshot["health"][number];
type ChannelRuntimeSummary = SiteRuntimeSummary["channel_summaries"][number];
export type ChannelHealthBucket =
  ChannelRuntimeSummary["health_buckets"][number];
export type CoolingBadgeSpec = {
  label: string;
  title: string;
  className: string;
};
export type HealthPreviewChannel = {
  channelId: string;
  protocolConfig: SiteRow["protocols"][number];
  protocolConfigIndex: number;
  protocol: ProtocolKind;
};

export const CHANNEL_HEALTH_BUCKET_COUNT = 12;

function credentialNamesById(site: SiteRow, locale: Locale) {
  return new Map(
    site.credentials.map(
      (item, index) =>
        [item.id, credentialDisplayName(item, index, locale)] as const,
    ),
  );
}

function maxKeyCooldownSeconds(health: ChannelHealthRow | undefined) {
  if (!health?.key_health?.length) {
    return 0;
  }
  return Math.max(
    0,
    ...health.key_health.map((item) => item.cooldown_remaining_seconds),
  );
}

function maxModelCooldownSeconds(health: ChannelHealthRow | undefined) {
  if (!health?.model_health?.length) {
    return 0;
  }
  return Math.max(
    0,
    ...health.model_health.map((item) => item.cooldown_remaining_seconds),
  );
}

function keyCooldownDetails(
  site: SiteRow,
  health: ChannelHealthRow,
  locale: Locale,
) {
  const credentialNameById = credentialNamesById(site, locale);

  return health.key_health
    .filter((item) => !item.available && item.cooldown_remaining_seconds > 0)
    .sort(
      (left, right) =>
        right.cooldown_remaining_seconds - left.cooldown_remaining_seconds,
    )
    .map((item) => {
      const credentialName =
        credentialNameById.get(item.credential_id) ??
        (item.credential_id ||
          (locale === "zh-CN" ? "默认凭证" : "Default credential"));
      const duration = formatCooldownDuration(item.cooldown_remaining_seconds);
      return `${credentialName} ${locale === "zh-CN" ? "冷却剩余" : "cooldown remaining"} ${duration}`;
    });
}

function modelCooldownDetails(health: ChannelHealthRow, locale: Locale) {
  return health.model_health
    .filter((item) => !item.available && item.cooldown_remaining_seconds > 0)
    .sort(
      (left, right) =>
        right.cooldown_remaining_seconds - left.cooldown_remaining_seconds,
    )
    .map((item) => {
      const duration = formatCooldownDuration(item.cooldown_remaining_seconds);
      const modelName =
        item.model_name ||
        (locale === "zh-CN" ? "未指定模型" : "Unspecified model");
      return `${modelName} ${locale === "zh-CN" ? "冷却剩余" : "cooldown remaining"} ${duration}`;
    });
}

/** Resolve the cooldown badge shown for a runtime channel. */
export function resolveCoolingBadge(
  site: SiteRow,
  health: ChannelHealthRow | undefined,
  locale: Locale,
): CoolingBadgeSpec | null {
  if (!health) {
    return null;
  }
  if (health.cooldown_remaining_seconds > 0) {
    const duration = formatCooldownDuration(health.cooldown_remaining_seconds);
    const details = [
      ...modelCooldownDetails(health, locale),
      ...keyCooldownDetails(site, health, locale),
    ];
    return locale === "zh-CN"
      ? {
          label: `渠道暂不可用 ${duration}`,
          title: [
            `没有可用的 Key + 模型绑定，最早恢复还需 ${duration}`,
            ...details,
          ].join("\n"),
          className: "border-transparent bg-destructive/12 text-destructive",
        }
      : {
          label: `Channel unavailable ${duration}`,
          title: [
            `No key-model binding is available; earliest recovery in ${duration}`,
            ...details,
          ].join("\n"),
          className: "border-transparent bg-destructive/12 text-destructive",
        };
  }
  const modelCooldownSeconds = maxModelCooldownSeconds(health);
  const keyCooldownSeconds = maxKeyCooldownSeconds(health);
  if (modelCooldownSeconds > 0 && keyCooldownSeconds > 0) {
    const duration = formatCooldownDuration(
      Math.max(modelCooldownSeconds, keyCooldownSeconds),
    );
    const details = [
      ...modelCooldownDetails(health, locale),
      ...keyCooldownDetails(site, health, locale),
    ].join("\n");
    return locale === "zh-CN"
      ? {
          label: `模型与 Key 冷却 ${duration}`,
          title: details,
          className: "border-transparent bg-amber-500/12 text-amber-700",
        }
      : {
          label: `Model & key cooling ${duration}`,
          title: details,
          className: "border-transparent bg-amber-500/12 text-amber-700",
        };
  }
  if (modelCooldownSeconds > 0) {
    const duration = formatCooldownDuration(modelCooldownSeconds);
    const details = modelCooldownDetails(health, locale).join("\n");
    return locale === "zh-CN"
      ? {
          label: `模型冷却 ${duration}`,
          title: details || `模型冷却剩余 ${duration}`,
          className: "border-transparent bg-amber-500/12 text-amber-700",
        }
      : {
          label: `Model cooling ${duration}`,
          title: details || `Model cooldown remaining ${duration}`,
          className: "border-transparent bg-amber-500/12 text-amber-700",
        };
  }
  if (keyCooldownSeconds <= 0) {
    return null;
  }
  const duration = formatCooldownDuration(keyCooldownSeconds);
  const details = keyCooldownDetails(site, health, locale).join("\n");
  return locale === "zh-CN"
    ? {
        label: `Key 冷却 ${duration}`,
        title: details || `Key 冷却剩余 ${duration}`,
        className: "border-transparent bg-amber-500/12 text-amber-700",
      }
    : {
        label: `Key cooling ${duration}`,
        title: details || `Key cooldown remaining ${duration}`,
        className: "border-transparent bg-amber-500/12 text-amber-700",
      };
}

/** Return enabled runtime channels represented by a site. */
export function siteHealthPreviewChannels(
  site: SiteRow,
): HealthPreviewChannel[] {
  return site.protocols.flatMap((protocolConfig, protocolConfigIndex) => {
    if (!protocolConfig.enabled) {
      return [];
    }
    return protocolConfig.protocols.map((protocol) => ({
      channelId: `${protocolConfig.id}_${protocol}`,
      protocolConfig,
      protocolConfigIndex,
      protocol,
    }));
  });
}

/** Format a compact runtime channel label. */
export function healthPreviewChannelLabel(
  channel: HealthPreviewChannel,
  locale: Locale,
) {
  return `${protocolConfigDisplayName(channel.protocolConfig, channel.protocolConfigIndex, locale)} / ${compactProtocolLabel(channel.protocol)}`;
}

/** Clamp a health bucket's success and total counts. */
export function normalizedBucketCounts(bucket: ChannelHealthBucket) {
  const total = Math.max(0, bucket.total_count);
  return {
    total,
    success: Math.min(Math.max(0, bucket.success_count), total),
  };
}

/** Return the visual tone for a health bucket. */
export function healthBucketTone(bucket: ChannelHealthBucket) {
  const { success, total } = normalizedBucketCounts(bucket);
  if (total <= 0) {
    return "bg-muted/70";
  }
  if (success >= total) {
    return "bg-emerald-500";
  }
  if (success > 0) {
    return "bg-amber-500";
  }
  return "bg-destructive";
}

/** Create the date formatter used by health bucket tooltips. */
export function createHealthBucketTimeFormatter(
  locale: Locale,
  timeZone?: string,
) {
  return new Intl.DateTimeFormat(locale === "zh-CN" ? "zh-CN" : "en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...(timeZone ? { timeZone } : {}),
  });
}

/** Format the start and end timestamps for a health bucket. */
export function formatHealthBucketRange(
  bucket: ChannelHealthBucket,
  formatDateTime: Intl.DateTimeFormat,
) {
  return `${formatDateTime.format(new Date(bucket.started_at))} - ${formatDateTime.format(new Date(bucket.ended_at))}`;
}
