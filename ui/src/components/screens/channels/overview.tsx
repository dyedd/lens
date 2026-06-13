"use client";

import type { Dispatch, SetStateAction } from "react";
import { Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";
import type {
  ProtocolKind,
  RouteSnapshot,
  Site,
  SiteRuntimeSummary,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { ChannelFiltersPanel } from "./filters";
import { SiteHealthPreview } from "./health-preview";
import {
  isSiteEnabled,
  protocolBadgeClassName,
  protocolLabel,
  SiteFavicon,
  siteProtocols,
  type ChannelSort,
  type ChannelStatusFilter,
  type Locale,
  type SiteRow,
} from "./shared";

export function ChannelsOverview({
  locale,
  visibleSites,
  isLoading,
  sitesIsError,
  siteRuntimeById,
  channelHealthById,
  timeZone,
  search,
  statusFilter,
  protocolFilter,
  sortBy,
  activeFilterCount,
  busyId,
  onSearchChange,
  onStatusChange,
  onProtocolChange,
  onSortChange,
  onReset,
  onOpenEdit,
  onToggleSiteEnabled,
  setDeleteTarget,
}: {
  locale: Locale;
  visibleSites: SiteRow[];
  isLoading: boolean;
  sitesIsError: boolean;
  siteRuntimeById: Map<string, SiteRuntimeSummary>;
  channelHealthById: Map<string, RouteSnapshot["health"][number]>;
  timeZone?: string;
  search: string;
  statusFilter: ChannelStatusFilter;
  protocolFilter: "all" | ProtocolKind;
  sortBy: ChannelSort;
  activeFilterCount: number;
  busyId: string | null;
  onSearchChange: Dispatch<SetStateAction<string>>;
  onStatusChange: Dispatch<SetStateAction<ChannelStatusFilter>>;
  onProtocolChange: Dispatch<SetStateAction<"all" | ProtocolKind>>;
  onSortChange: Dispatch<SetStateAction<ChannelSort>>;
  onReset: () => void;
  onOpenEdit: (site: Site) => void;
  onToggleSiteEnabled: (site: Site, enabled: boolean) => void;
  setDeleteTarget: Dispatch<SetStateAction<Site | null>>;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_320px]">
      <Card className="overflow-hidden py-0 xl:min-h-[calc(100dvh-7.5rem)]">
        <CardContent className="px-3 py-3 xl:max-h-[calc(100dvh-7.5rem)] xl:overflow-y-auto">
          {isLoading || sitesIsError ? null : visibleSites.length ? (
            <ItemGroup className="gap-3">
              {visibleSites.map((site) => {
                const runtimeSummary = siteRuntimeById.get(site.id);
                return (
                  <Item
                    key={site.id}
                    variant="outline"
                    role="button"
                    tabIndex={0}
                    className="items-start gap-3 rounded-2xl border-border/80 bg-gradient-to-r from-background to-muted/[0.18] px-4 py-4 shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer sm:gap-4 sm:px-5 sm:py-5"
                    onClick={() => onOpenEdit(site)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onOpenEdit(site);
                      }
                    }}
                  >
                    <ItemMedia
                      variant="icon"
                      className="mt-0.5 hidden self-start sm:flex"
                    >
                      <SiteFavicon
                        key={site.endpoint_summary}
                        url={site.endpoint_summary}
                        name={site.name}
                      />
                    </ItemMedia>
                    <ItemContent className="min-w-0">
                      <div className="flex flex-col gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <ItemTitle className="truncate text-base">
                            {site.name}
                          </ItemTitle>
                          {siteProtocols(site).map((p) => (
                            <Badge
                              key={p}
                              variant="outline"
                              className={cn(
                                "px-2.5 py-0.5",
                                protocolBadgeClassName(p),
                              )}
                            >
                              {protocolLabel(p)}
                            </Badge>
                          ))}
                        </div>
                        <ItemDescription className="truncate text-sm">
                          {site.endpoint_summary ||
                            (locale === "zh-CN"
                              ? "未配置请求地址"
                              : "No endpoint configured")}
                        </ItemDescription>
                        <SiteHealthPreview
                          site={site}
                          summary={runtimeSummary}
                          healthByChannelId={channelHealthById}
                          locale={locale}
                          timeZone={timeZone}
                        />
                      </div>
                    </ItemContent>
                    <ItemActions
                      className="basis-full flex-wrap justify-end self-start sm:ml-auto sm:basis-auto sm:shrink-0"
                      onClick={(event) => event.stopPropagation()}
                      onKeyDown={(event) => event.stopPropagation()}
                    >
                      <Switch
                        checked={isSiteEnabled(site)}
                        disabled={busyId === site.id}
                        onCheckedChange={(checked) =>
                          void onToggleSiteEnabled(site, checked)
                        }
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="rounded-full text-destructive hover:text-destructive"
                        onClick={() => setDeleteTarget(site)}
                      >
                        <Trash2 data-icon="inline-start" />
                        {locale === "zh-CN" ? "删除" : "Delete"}
                      </Button>
                    </ItemActions>
                  </Item>
                );
              })}
            </ItemGroup>
          ) : (
            <div className="rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">
              {search.trim()
                ? locale === "zh-CN"
                  ? "没有匹配的渠道。"
                  : "No matching channels."
                : locale === "zh-CN"
                  ? "当前还没有渠道。"
                  : "No channels yet."}
            </div>
          )}
        </CardContent>
      </Card>

      <aside className="order-1 xl:order-2">
        <ChannelFiltersPanel
          locale={locale}
          search={search}
          statusFilter={statusFilter}
          protocolFilter={protocolFilter}
          sortBy={sortBy}
          activeFilterCount={activeFilterCount}
          onSearchChange={onSearchChange}
          onStatusChange={onStatusChange}
          onProtocolChange={onProtocolChange}
          onSortChange={onSortChange}
          onReset={onReset}
        />
      </aside>
    </div>
  );
}
