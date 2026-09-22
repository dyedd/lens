import { Check, Clock, Funnel, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { Input } from "@/components/ui/Input";
import { TablePagination } from "@/components/ui/Pagination";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { ToolbarButton } from "@/components/ui/ToolbarButton";
import type { HealthItem } from "@/lib/api/sites";
import { cn } from "@/lib/classNames";
import { titleForLocale } from "@/lib/I18nContext";
import { HealthTable } from "./HealthTable";
import {
  HEALTH_HOURS,
  type HealthHours,
  type HealthMode,
  hoursLabel,
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
    : titleForLocale(locale, "暂无健康数据。", "No health data yet.");

  return (
    <div className="space-y-3 pb-10">
      <div className="flex h-10 items-center justify-between gap-3 px-1">
        <h3 className="text-sm font-semibold">
          {titleForLocale(locale, "模型组健康", "Model group health")}
        </h3>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 gap-1.5 px-2 text-xs text-muted-foreground shadow-none hover:bg-muted hover:text-foreground data-[state=open]:bg-muted data-[state=open]:text-foreground"
            >
              <Clock className="size-3.5 stroke-1" />
              {hoursLabel(hours, locale)}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-36 p-1.5">
            {HEALTH_HOURS.map((option) => (
              <DropdownMenuItem
                key={option.value}
                className="h-6 gap-2 px-2 py-0 text-[10px]"
                onSelect={() => onHoursChange(option.value)}
              >
                <span className="flex-1 truncate">
                  {locale === "zh-CN" ? option.zh : option.en}
                </span>
                {hours === option.value ? (
                  <Check className="size-3 text-muted-foreground" />
                ) : null}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <section className="flex min-h-10 flex-nowrap items-center gap-1.5 overflow-x-auto overscroll-x-contain py-1 [scrollbar-width:none] md:gap-3 [&::-webkit-scrollbar]:hidden">
        <div className="flex min-w-max flex-nowrap items-center gap-1.5 md:min-w-0 md:flex-1">
          <div className="relative min-w-[160px] flex-1 md:max-w-[320px]">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              placeholder={
                mode === "model"
                  ? titleForLocale(
                      locale,
                      "搜索模型组名称",
                      "Search model group names",
                    )
                  : titleForLocale(
                      locale,
                      "搜索渠道名称",
                      "Search channel names",
                    )
              }
              onChange={(event) => onSearchChange(event.target.value)}
              className="bg-background pl-8"
            />
          </div>

          <Popover>
            <PopoverTrigger asChild>
              <ToolbarButton
                aria-label={titleForLocale(locale, "筛选", "Filter")}
              >
                <Funnel className="size-3.5" />
                <span className="hidden sm:inline">
                  {titleForLocale(locale, "筛选", "Filter")}
                </span>
                {activeFilterCount ? (
                  <span className="text-[10px] tabular-nums">
                    {activeFilterCount}
                  </span>
                ) : null}
              </ToolbarButton>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-[240px] p-2">
              <div className="space-y-2">
                <div className="space-y-1">
                  <p className="px-1 text-[10px] text-muted-foreground">
                    {titleForLocale(locale, "维度", "Dimension")}
                  </p>
                  <Select
                    value={mode}
                    onValueChange={(value) => onModeChange(value as HealthMode)}
                  >
                    <SelectTrigger className="h-7 px-2 text-[11px] text-muted-foreground">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="model">
                        {titleForLocale(locale, "模型组", "Model groups")}
                      </SelectItem>
                      <SelectItem value="channel">
                        {titleForLocale(locale, "渠道", "Channels")}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {activeFilterCount ? (
                  <div className="flex justify-end border-t border-border/60 pt-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs shadow-none"
                      onClick={onReset}
                    >
                      {titleForLocale(locale, "清空", "Clear")}
                    </Button>
                  </div>
                ) : null}
              </div>
            </PopoverContent>
          </Popover>
        </div>

        <div className="ml-auto flex min-h-8 shrink-0 items-center gap-1">
          <ToolbarButton
            onClick={onRefresh}
            disabled={fetching}
            aria-label={titleForLocale(locale, "刷新", "Refresh")}
            title={titleForLocale(locale, "刷新", "Refresh")}
          >
            <RefreshCw className={cn("size-3.5", fetching && "animate-spin")} />
          </ToolbarButton>
        </div>
      </section>

      <HealthTable
        locale={locale}
        mode={mode}
        items={items}
        loading={loading}
        emptyLabel={emptyLabel}
        timeZone={timeZone}
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
