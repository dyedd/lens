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

function maxKeyCooldownSeconds(health: ChannelHealthRow | undefined) {
  if (!health?.key_health?.length) {
    return 0;
  }
  return Math.max(
    0,
    ...health.key_health.map((item) => item.cooldown_remaining_seconds),
  );
}

function keyCooldownDetails(
  site: SiteRow,
  health: ChannelHealthRow,
  locale: Locale,
) {
  const credentialById = new Map(
    site.credentials.map((item) => [item.id, item] as const),
  );
  const credentialIndexById = new Map(
    site.credentials.map((item, index) => [item.id, index] as const),
  );

  return health.key_health
    .filter((item) => !item.available && item.cooldown_remaining_seconds > 0)
    .sort(
      (left, right) =>
        right.cooldown_remaining_seconds - left.cooldown_remaining_seconds,
    )
    .map((item) => {
      const credentialIndex = credentialIndexById.get(item.credential_id) ?? 0;
      const credentialName = credentialDisplayName(
        credentialById.get(item.credential_id),
        credentialIndex,
        locale,
      );
      const duration = formatCooldownDuration(item.cooldown_remaining_seconds);
      return `${credentialName} ${locale === "zh-CN" ? "冷却剩余" : "cooldown remaining"} ${duration}`;
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
    return locale === "zh-CN"
      ? {
          label: `冷却 ${duration}`,
          title: `渠道冷却剩余 ${duration}`,
          className: "border-transparent bg-destructive/12 text-destructive",
        }
      : {
          label: `Cooling ${duration}`,
          title: `Channel cooldown remaining ${duration}`,
          className: "border-transparent bg-destructive/12 text-destructive",
        };
  }
  const keyCooldownSeconds = maxKeyCooldownSeconds(health);
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
