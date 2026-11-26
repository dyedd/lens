import { RefreshCw, Search } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { FilterPillGroup } from "@/components/ui/FilterPillGroup";
import { Input } from "@/components/ui/Input";
import { TablePagination } from "@/components/ui/Pagination";
import type { HealthItem } from "@/lib/api/sites";
import { cn } from "@/lib/classNames";
import { titleForLocale } from "@/lib/I18nContext";
import { HealthTable } from "./HealthTable";
import {
  HEALTH_HOURS,
  type HealthHours,
  type HealthMode,
  type Locale,
  PAGE_SIZE_OPTIONS,
} from "./healthView";

type Props = {
  locale: Locale;
  items: HealthItem[];
  loading: boolean;
  fetching: boolean;
  search: string;
  mode: HealthMode;
  hours: HealthHours;
  page: number;
  pageSize: (typeof PAGE_SIZE_OPTIONS)[number];
  hasNextPage: boolean;
  timeZone: string;
  isResettingCooldown: boolean;
  onResetCooldown: (id: string) => void;
  onSearchChange: (value: string) => void;
  onModeChange: (value: HealthMode) => void;
  onHoursChange: (value: HealthHours) => void;
  onReset: () => void;
  onRefresh: () => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: (typeof PAGE_SIZE_OPTIONS)[number]) => void;
};

/** Renders model-group health as a toolbar and table. */
export function HealthOverview({
  locale,
  items,
  loading,
  fetching,
  search,
  mode,
  hours,
  page,
  pageSize,
  hasNextPage,
  timeZone,
  isResettingCooldown,
  onResetCooldown,
  onSearchChange,
  onModeChange,
  onHoursChange,
  onReset,
  onRefresh,
  onPageChange,
  onPageSizeChange,
}: Props) {
  const displayPage = page + 1;
  const activeFilterCount = Number(mode !== "model");
  const emptyLabel = search.trim()
    ? titleForLocale(
        locale,
        "当前筛选条件下没有健康数据。",
        "No matching health data.",
      )
    : titleForLocale(locale, "健康状态", "Health status");
  const searchPlaceholder =
    mode === "model"
      ? titleForLocale(locale, "搜索模型组...", "Search model groups...")
      : titleForLocale(locale, "搜索渠道...", "Search channels...");

  return (
    <div className="space-y-4 pb-10">
      <PageHeader
        title={titleForLocale(locale, "健康状态", "Health status")}
        actions={
          <>
            <FilterPillGroup
              value={String(hours)}
              ariaLabel={titleForLocale(locale, "观测窗口", "Time window")}
              onValueChange={(value) => {
                const matched = HEALTH_HOURS.find(
                  (option) => String(option.value) === value,
                );
                if (matched) onHoursChange(matched.value);
              }}
              options={HEALTH_HOURS.map((option) => ({
                value: String(option.value),
                label: locale === "zh-CN" ? option.zh : option.en,
              }))}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
              onClick={onRefresh}
              disabled={fetching}
              aria-label={titleForLocale(locale, "刷新", "Refresh")}
            >
              <RefreshCw
                className={cn("size-3.5", fetching && "animate-spin")}
              />
              {titleForLocale(locale, "刷新", "Refresh")}
            </Button>
          </>
        }
      />

      <section className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <FilterPillGroup
            value={mode}
            ariaLabel={titleForLocale(locale, "观测维度", "Dimension")}
            onValueChange={(value) => onModeChange(value as HealthMode)}
            options={[
              {
                value: "model",
                label: titleForLocale(locale, "模型组", "Model groups"),
              },
              {
                value: "channel",
                label: titleForLocale(locale, "渠道", "Channels"),
              },
            ]}
          />
          {activeFilterCount ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-[13px] text-muted-foreground"
              onClick={onReset}
            >
              {titleForLocale(locale, "重置", "Reset")}
            </Button>
          ) : null}
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            onChange={(event) => onSearchChange(event.target.value)}
            className="pl-8"
          />
        </div>
      </section>

      <HealthTable
        locale={locale}
        mode={mode}
        items={items}
        loading={loading}
        emptyLabel={emptyLabel}
        timeZone={timeZone}
        isResettingCooldown={isResettingCooldown}
        onResetCooldown={onResetCooldown}
      />

      <TablePagination
        locale={locale}
        total={page * pageSize + items.length}
        page={displayPage}
        pageCount={hasNextPage ? displayPage + 1 : Math.max(1, displayPage)}
        pageSize={pageSize}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        onPageChange={(nextPage) => onPageChange(nextPage - 1)}
        onPageSizeChange={(size) =>
          onPageSizeChange(size as (typeof PAGE_SIZE_OPTIONS)[number])
        }
        loading={loading}
      />
    </div>
  );
}
