"use client";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type {
  ProtocolKind,
  RouteSnapshot,
  SiteRuntimeSummary,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  compactProtocolLabel,
  credentialDisplayName,
  formatCooldownDuration,
  protocolConfigDisplayName,
  type Locale,
  type SiteRow,
} from "./shared";

type ChannelHealthRow = RouteSnapshot["health"][number];
type ChannelRuntimeSummary = SiteRuntimeSummary["channel_summaries"][number];
type ChannelHealthBucket = ChannelRuntimeSummary["health_buckets"][number];
type CoolingBadgeSpec = {
  label: string;
  title: string;
  className: string;
};
type HealthPreviewChannel = {
  channelId: string;
  protocolConfig: SiteRow["protocols"][number];
  protocolConfigIndex: number;
  protocol: ProtocolKind;
};

const CHANNEL_HEALTH_BUCKET_COUNT = 12;

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

function resolveCoolingBadge(
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
  if (keyCooldownSeconds > 0) {
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
  return null;
}

function runtimeChannelId(protocolConfigId: string, protocol: ProtocolKind) {
  return `${protocolConfigId}_${protocol}`;
}

function siteHealthPreviewChannels(site: SiteRow): HealthPreviewChannel[] {
  return site.protocols.flatMap((protocolConfig, protocolConfigIndex) => {
    if (!protocolConfig.enabled) {
      return [];
    }
    return protocolConfig.protocols.map((protocol) => ({
      channelId: runtimeChannelId(protocolConfig.id, protocol),
      protocolConfig,
      protocolConfigIndex,
      protocol,
    }));
  });
}

function healthPreviewChannelLabel(
  channel: HealthPreviewChannel,
  locale: Locale,
) {
  return `${protocolConfigDisplayName(channel.protocolConfig, channel.protocolConfigIndex, locale)} / ${compactProtocolLabel(channel.protocol)}`;
}

function normalizedBucketCounts(bucket: ChannelHealthBucket) {
  const total = Math.max(0, bucket.total_count);
  return {
    total,
    success: Math.min(Math.max(0, bucket.success_count), total),
  };
}

function healthBucketTone(bucket: ChannelHealthBucket) {
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

function createHealthBucketTimeFormatter(locale: Locale, timeZone?: string) {
  return new Intl.DateTimeFormat(locale === "zh-CN" ? "zh-CN" : "en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...(timeZone ? { timeZone } : {}),
  });
}

function formatHealthBucketRange(
  bucket: ChannelHealthBucket,
  formatDateTime: Intl.DateTimeFormat,
) {
  return `${formatDateTime.format(new Date(bucket.started_at))} - ${formatDateTime.format(new Date(bucket.ended_at))}`;
}

export function SiteHealthPreview({
  site,
  summary,
  healthByChannelId,
  locale,
  timeZone,
}: {
  site: SiteRow;
  summary?: SiteRuntimeSummary;
  healthByChannelId: Map<string, ChannelHealthRow>;
  locale: Locale;
  timeZone?: string;
}) {
  const channels = siteHealthPreviewChannels(site);
  const summaryByChannelId = new Map(
    (summary?.channel_summaries ?? []).map(
      (item) => [item.channel_id, item] as const,
    ),
  );
  const multiChannel = channels.length > 1;
  const bucketTimeFormatter = createHealthBucketTimeFormatter(locale, timeZone);

  if (!channels.length) {
    return (
      <div className="mt-3 text-xs text-muted-foreground">
        {locale === "zh-CN" ? "暂无健康数据" : "No health data"}
      </div>
    );
  }

  return (
    <div className="mt-3 flex flex-col gap-2.5">
      <div className="text-xs font-medium text-muted-foreground">
        {locale === "zh-CN" ? "健康状态" : "Health"}
      </div>
      {channels.map((channel) => {
        const health = healthByChannelId.get(channel.channelId);
        const channelSummary = summaryByChannelId.get(channel.channelId);
        const buckets = (channelSummary?.health_buckets ?? []).slice(
          -CHANNEL_HEALTH_BUCKET_COUNT,
        );
        const coolingBadge = resolveCoolingBadge(site, health, locale);
        const segments = [
          ...Array.from(
            {
              length: Math.max(CHANNEL_HEALTH_BUCKET_COUNT - buckets.length, 0),
            },
            (_, index) => ({
              key: `${channel.channelId}-placeholder-${index}`,
              bucket: null,
            }),
          ),
          ...buckets.map((bucket, index) => ({
            key: `${channel.channelId}-bucket-${bucket.started_at}-${index}`,
            bucket,
          })),
        ];

        return (
          <div
            key={channel.channelId}
            className="flex min-w-0 flex-wrap items-center gap-3 py-0.5"
          >
            {multiChannel ? (
              <span className="w-28 min-w-0 shrink-0 truncate text-[11px] font-medium text-muted-foreground">
                {healthPreviewChannelLabel(channel, locale)}
              </span>
            ) : null}

            <div
              className="flex min-w-0 flex-1 items-end gap-1"
              aria-label={locale === "zh-CN" ? "健康状态" : "health history"}
            >
              {segments.map((segment) => {
                if (!segment.bucket) {
                  return (
                    <span
                      key={segment.key}
                      className="block h-6 w-1.5 rounded-[3px] bg-muted/70"
                      aria-hidden
                    />
                  );
                }

                const { success, total } = normalizedBucketCounts(
                  segment.bucket,
                );
                const bucketRange = formatHealthBucketRange(
                  segment.bucket,
                  bucketTimeFormatter,
                );

                const tooltipContent = (
                  <TooltipContent
                    side="bottom"
                    sideOffset={8}
                    collisionPadding={12}
                    className="flex flex-col items-start gap-1 px-3 py-2 text-left text-xs"
                  >
                    <div className="font-medium">{bucketRange}</div>
                    <div className="text-muted-foreground">
                      {locale === "zh-CN" ? "成功" : "Success"}: {success}/
                      {total}
                    </div>
                  </TooltipContent>
                );

                const segmentClassName = cn(
                  "block h-6 w-1.5 appearance-none rounded-[3px] border-0 p-0",
                  healthBucketTone(segment.bucket),
                );

                return (
                  <Tooltip key={segment.key}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className={cn(
                          segmentClassName,
                          "outline-none transition-transform hover:scale-y-110 focus-visible:ring-2 focus-visible:ring-ring/70 focus-visible:ring-offset-1",
                        )}
                        onClick={(event) => event.stopPropagation()}
                        onKeyDown={(event) => event.stopPropagation()}
                        aria-label={`${bucketRange} ${success}/${total}`}
                      />
                    </TooltipTrigger>
                    {tooltipContent}
                  </Tooltip>
                );
              })}
            </div>

            <div className="flex w-full min-w-0 flex-wrap items-center gap-2 sm:ml-auto sm:w-auto sm:shrink-0">
              {coolingBadge ? (
                <Badge
                  variant="outline"
                  title={coolingBadge.title}
                  className={cn(
                    "max-w-full truncate px-2.5 py-1 text-xs",
                    coolingBadge.className,
                  )}
                >
                  {coolingBadge.label}
                </Badge>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
