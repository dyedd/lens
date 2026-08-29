import { ArrowUp, RefreshCcw } from "lucide-react";

import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { cn } from "@/lib/classNames";
import { titleForLocale } from "@/lib/I18nContext";

import { RequestFiltersPanel } from "./requests/RequestFiltersPanel";
import { RequestLogDialogs } from "./requests/RequestLogDialogs";
import { RequestLogResults } from "./requests/RequestLogResults";
import { RequestPagination } from "./requests/RequestPagination";
import { useRequestsScreen } from "./requests/useRequestsScreen";

/** Render searchable request logs and request details. */
export function RequestsScreen() {
  const screen = useRequestsScreen();
  const isPlaceholderData = screen.logsQuery.isPlaceholderData;
  return (
    <TooltipProvider>
      <DashboardHeaderActions>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={titleForLocale(screen.locale, "刷新", "Refresh")}
              onClick={() => void screen.refreshLogs()}
              disabled={screen.logsQuery.isFetching}
            >
              <RefreshCcw
                data-icon="inline-start"
                className={cn(screen.logsQuery.isFetching && "animate-spin")}
              />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom" align="end">
            {titleForLocale(screen.locale, "刷新", "Refresh")}
          </TooltipContent>
        </Tooltip>
      </DashboardHeaderActions>
      <section className="flex flex-col gap-4 md:gap-5">
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,4fr)_320px]">
          <RequestLogResults
            activeFilterCount={screen.activeFilterCount}
            canOpenDetail={screen.relayLogBodyEnabled}
            effectiveModelPrefix={screen.effectiveModelPrefix}
            isError={screen.logsQuery.isError}
            isLoading={screen.logsQuery.isLoading || isPlaceholderData}
            items={
              isPlaceholderData ? [] : (screen.logsQuery.data?.items ?? [])
            }
            locale={screen.locale}
            modelPrefixOptions={screen.modelPrefixOptions}
            showModelPrefixFilter={screen.modelPrefixOptions.length > 1}
            timeZone={screen.timeZone}
            onModelPrefixChange={(value) =>
              screen.updateFilter(() => screen.setSelectedModelPrefix(value))
            }
            onOpenAttempts={screen.setAttemptDetailId}
            onOpenDetail={screen.setDetailId}
          />
          <RequestFiltersPanel
            activeFilterCount={screen.activeFilterCount}
            channelFilter={screen.channelFilter}
            channelOptions={screen.channelOptions}
            clearingLogs={screen.clearingLogs}
            gatewayKeyOptions={screen.gatewayKeyOptions}
            keyword={screen.keyword}
            locale={screen.locale}
            protocolFilter={screen.protocolFilter}
            selectedGatewayKeyId={screen.selectedGatewayKeyId}
            showGatewayKeyFilter={
              Boolean(screen.logsQuery.data?.gateway_has_multiple_keys) ||
              screen.gatewayKeyId !== null
            }
            sortMode={screen.sortMode}
            statusFilter={screen.statusFilter}
            onChannelChange={(value) =>
              screen.updateFilter(() => screen.setChannelFilter(value))
            }
            onClear={() => void screen.clearRequestLogs()}
            onGatewayKeyChange={(value) =>
              screen.updateFilter(() => screen.setSelectedGatewayKeyId(value))
            }
            onKeywordChange={(value) =>
              screen.updateFilter(() => screen.setKeyword(value))
            }
            onProtocolChange={(value) =>
              screen.updateFilter(() => screen.setProtocolFilter(value))
            }
            onSortChange={(value) =>
              screen.updateFilter(() => screen.setSortMode(value))
            }
            onStatusChange={(value) =>
              screen.updateFilter(() => screen.setStatusFilter(value))
            }
          />
        </div>
        <RequestPagination
          hasNextPage={screen.page < screen.totalPages - 1}
          locale={screen.locale}
          page={screen.page}
          paginationItems={screen.paginationItems}
          totalPages={screen.totalPages}
          onPageChange={screen.setPage}
        />
        <RequestLogDialogs
          attemptDetailId={screen.attemptDetailId}
          attemptState={screen.attemptQuery}
          detailId={screen.detailId}
          detailState={screen.detailQuery}
          locale={screen.locale}
          relayLogBodyEnabled={screen.relayLogBodyEnabled}
          onAttemptClose={() => screen.setAttemptDetailId(null)}
          onDetailClose={() => screen.setDetailId(null)}
        />
        {screen.showBackToTop ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="icon-lg"
                className="fixed right-4 bottom-4 z-40 rounded-full shadow-sm sm:right-6 sm:bottom-6"
                onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              >
                <ArrowUp />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">
              {titleForLocale(screen.locale, "返回顶部", "Back to top")}
            </TooltipContent>
          </Tooltip>
        ) : null}
      </section>
    </TooltipProvider>
  );
}
