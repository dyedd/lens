import { ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { titleForLocale } from "@/lib/I18nContext";
import { RequestLogDetailSheet } from "./requests/RequestLogDetailSheet";
import { RequestsOverview } from "./requests/RequestsOverview";
import { useRequestsScreen } from "./requests/useRequestsScreen";

/** Render searchable request logs and request details. */
export function RequestsScreen() {
  const screen = useRequestsScreen();
  const selectedItem =
    screen.logsQuery.data?.items.find((item) => item.id === screen.detailId) ??
    screen.detailQuery.data ??
    null;
  return (
    <TooltipProvider>
      <RequestsOverview
        locale={screen.locale}
        items={screen.logsQuery.data?.items ?? []}
        loading={screen.logsQuery.isLoading}
        fetching={screen.logsQuery.isFetching}
        keyword={screen.keyword}
        statusFilter={screen.statusFilter}
        protocolFilter={screen.protocolFilter}
        channelFilter={screen.channelFilter}
        channelOptions={screen.channelOptions}
        selectedGatewayKeyId={screen.selectedGatewayKeyId}
        gatewayKeyOptions={screen.gatewayKeyOptions}
        showGatewayKeyFilter={
          Boolean(screen.logsQuery.data?.gateway_has_multiple_keys) ||
          screen.gatewayKeyId !== null
        }
        modelPrefixOptions={screen.modelPrefixOptions}
        effectiveModelPrefix={screen.effectiveModelPrefix}
        sortMode={screen.sortMode}
        activeFilterCount={screen.activeFilterCount}
        clearingLogs={screen.clearingLogs}
        timeZone={screen.timeZone}
        page={screen.page}
        pageSize={screen.pageSize}
        total={screen.total}
        totalPages={screen.totalPages}
        onKeywordChange={(value) =>
          screen.updateFilter(() => screen.setKeyword(value))
        }
        onStatusChange={(value) =>
          screen.updateFilter(() => screen.setStatusFilter(value))
        }
        onProtocolChange={(value) =>
          screen.updateFilter(() => screen.setProtocolFilter(value))
        }
        onChannelChange={(value) =>
          screen.updateFilter(() => screen.setChannelFilter(value))
        }
        onGatewayKeyChange={(value) =>
          screen.updateFilter(() => screen.setSelectedGatewayKeyId(value))
        }
        onModelPrefixChange={(value) =>
          screen.updateFilter(() => screen.setSelectedModelPrefix(value))
        }
        onSortChange={(value) =>
          screen.updateFilter(() => screen.setSortMode(value))
        }
        onReset={screen.resetFilters}
        onRefresh={() => void screen.refreshLogs()}
        onClear={() => void screen.clearRequestLogs()}
        onPageChange={screen.setPage}
        onPageSizeChange={screen.changePageSize}
        onOpenDetail={screen.setDetailId}
      />
      <RequestLogDetailSheet
        item={selectedItem}
        detail={screen.detailQuery.data}
        loading={screen.detailQuery.isLoading}
        error={screen.detailQuery.error}
        locale={screen.locale}
        timeZone={screen.timeZone}
        relayLogBodyEnabled={screen.relayLogBodyEnabled}
        onClose={() => screen.setDetailId(null)}
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
    </TooltipProvider>
  );
}
