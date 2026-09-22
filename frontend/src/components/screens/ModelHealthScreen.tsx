import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { apiRequest } from "@/lib/api/client";
import type { HealthSummary } from "@/lib/api/sites";
import { titleForLocale, useI18n } from "@/lib/I18nContext";
import { HealthOverview } from "./health/HealthOverview";
import {
  type HealthHours,
  type HealthMode,
  type PAGE_SIZE_OPTIONS,
  SEARCH_DEBOUNCE_MS,
} from "./health/healthView";

function useDebouncedValue(value: string, delay: number) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedValue(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);

  return debouncedValue;
}

/** Renders request-log health by execution model group or configured channel. */
export function ModelHealthScreen() {
  const { locale } = useI18n();
  const timeZone = useAppTimeZone();
  const [hours, setHours] = useState<HealthHours>("6");
  const [mode, setMode] = useState<HealthMode>("model");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] =
    useState<(typeof PAGE_SIZE_OPTIONS)[number]>(25);
  const debouncedSearch = useDebouncedValue(search.trim(), SEARCH_DEBOUNCE_MS);
  const offset = page * pageSize;
  const healthQuery = useQuery({
    queryKey: ["model-health", mode, hours, debouncedSearch, pageSize, offset],
    queryFn: () => {
      const query = new URLSearchParams({
        hours,
        mode,
        limit: String(pageSize),
        offset: String(offset),
      });
      if (debouncedSearch) query.set("query", debouncedSearch);
      return apiRequest<HealthSummary>(
        `/admin/model-health?${query.toString()}`,
      );
    },
    placeholderData: keepPreviousData,
    staleTime: 5_000,
    refetchInterval: 5_000,
  });

  useEffect(() => {
    if (!healthQuery.isError) return;
    toast.error(
      titleForLocale(locale, "健康数据加载失败", "Failed to load health data"),
      {
        id: "model-health-load-error",
        description:
          healthQuery.error instanceof Error
            ? healthQuery.error.message
            : titleForLocale(
                locale,
                "无法读取请求日志健康统计",
                "Unable to read request-log health statistics",
              ),
      },
    );
  }, [healthQuery.error, healthQuery.isError, locale]);

  function updateFilter(callback: () => void) {
    callback();
    setPage(0);
  }

  return (
    <TooltipProvider>
      <HealthOverview
        locale={locale}
        items={healthQuery.data?.items ?? []}
        loading={healthQuery.isLoading}
        fetching={healthQuery.isFetching}
        search={search}
        mode={mode}
        hours={hours}
        page={page}
        pageSize={pageSize}
        hasNextPage={healthQuery.data?.next_offset != null}
        timeZone={timeZone}
        onSearchChange={(value) =>
          updateFilter(() => {
            setSearch(value);
          })
        }
        onModeChange={(value) =>
          updateFilter(() => {
            setMode(value);
          })
        }
        onHoursChange={(value) =>
          updateFilter(() => {
            setHours(value);
          })
        }
        onReset={() =>
          updateFilter(() => {
            setMode("model");
          })
        }
        onRefresh={() => void healthQuery.refetch()}
        onPageChange={setPage}
        onPageSizeChange={(size) =>
          updateFilter(() => {
            setPageSize(size);
          })
        }
      />
    </TooltipProvider>
  );
}
