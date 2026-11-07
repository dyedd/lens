import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { useAppTimeZone } from "@/hooks/useAppTimeZone";
import { apiFetch, apiRequest, getApiErrorMessage } from "@/lib/api/client";
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
  const queryClient = useQueryClient();
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
    queryFn: ({ signal }) => {
      const query = new URLSearchParams({
        hours,
        mode,
        limit: String(pageSize),
        offset: String(offset),
      });
      if (debouncedSearch) query.set("query", debouncedSearch);
      return apiRequest<HealthSummary>(
        `/admin/model-health?${query.toString()}`,
        { signal },
      );
    },
    placeholderData: keepPreviousData,
    staleTime: 5_000,
    refetchInterval: 5_000,
  });
  const resetCooldown = useMutation({
    mutationFn: ({ id, mode }: { id: string; mode: HealthMode }) =>
      apiFetch(
        `/admin/model-health/${encodeURIComponent(id)}/reset-cooldown?mode=${mode}`,
        { method: "POST" },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["model-health"] });
      toast.success(titleForLocale(locale, "冷却已重置", "Cooldown reset"));
    },
    onError: (error) => {
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(locale, "重置冷却失败", "Failed to reset cooldown"),
        ),
      );
    },
  });

  useEffect(() => {
    if (!healthQuery.isError) return;
    toast.error(
      titleForLocale(
        locale,
        "健康状态加载失败",
        "Failed to load health status",
      ),
      {
        id: "model-health-load-error",
        description:
          healthQuery.error instanceof Error
            ? healthQuery.error.message
            : titleForLocale(
                locale,
                "无法读取健康状态数据",
                "Unable to read health status data",
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
        isResettingCooldown={
          resetCooldown.isPending || healthQuery.isPlaceholderData
        }
        onResetCooldown={(id) => resetCooldown.mutate({ id, mode })}
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
