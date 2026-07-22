"use client";

import { Badge } from "@/components/ui/Badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { SiteRuntimeSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Locale, SiteRow } from "./channelShared";
import {
  CHANNEL_HEALTH_BUCKET_COUNT,
  createHealthBucketTimeFormatter,
  formatHealthBucketRange,
  healthBucketTone,
  healthPreviewChannelLabel,
  normalizedBucketCounts,
  resolveCoolingBadge,
  siteHealthPreviewChannels,
  type ChannelHealthRow,
} from "./siteHealthUtils";

/** Renders recent health buckets and cooldown details for a site. */
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
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="max-w-full rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring/70 focus-visible:ring-offset-1"
                      aria-label={coolingBadge.title.replaceAll("\n", ", ")}
                      onClick={(event) => event.stopPropagation()}
                      onKeyDown={(event) => event.stopPropagation()}
                    >
                      <Badge
                        variant="outline"
                        className={cn(
                          "max-w-full truncate px-2.5 py-1 text-xs",
                          coolingBadge.className,
                        )}
                      >
                        {coolingBadge.label}
                      </Badge>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent
                    sideOffset={8}
                    collisionPadding={12}
                    className="whitespace-pre-line text-left"
                  >
                    {coolingBadge.title}
                  </TooltipContent>
                </Tooltip>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
