import { ChevronDown, ChevronRight } from "lucide-react";
import { Fragment, useMemo, useState } from "react";
import { Link } from "react-router";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/Chart";
import { TablePagination } from "@/components/ui/Pagination";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type {
  AttributionDimension,
  OverviewAttribution,
  OverviewAttributionItem,
} from "@/lib/api/overview";
import type { Locale } from "@/lib/I18nContext";
import {
  type AnalysisMetric,
  formatCompact,
  formatDuration,
  formatMoney,
  formatTrendLabel,
  requestLogsHref,
  type TimeRange,
} from "./overviewMetrics";

type Props = {
  timeRange: TimeRange;
  analytics?: OverviewAttribution;
  dimension: AttributionDimension;
  onDimensionChange: (dimension: AttributionDimension) => void;
  filterKey: string | null;
  onFilterChange: (key: string | null) => void;
  metric: AnalysisMetric;
  onMetricChange: (metric: AnalysisMetric) => void;
  locale: Locale;
  isLoading: boolean;
  isError: boolean;
};

export function ModelAnalyticsCard({
  timeRange,
  analytics,
  dimension,
  onDimensionChange,
  filterKey,
  onFilterChange,
  metric,
  onMetricChange,
  locale,
  isLoading,
  isError,
}: Props) {
  const zh = locale === "zh-CN";
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [filterOpen, setFilterOpen] = useState(false);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  type SortField =
    | "requests"
    | "success"
    | "cache_hit_rate"
    | "total_tokens"
    | "total_cost_usd"
    | "wait_time_ms";
  const [sort, setSort] = useState<{ field: SortField; ascending: boolean }>({
    field: "requests",
    ascending: false,
  });
  const successRate = (row: OverviewAttributionItem) => {
    const completed = row.successful_requests + row.failed_requests;
    return completed ? row.successful_requests / completed : null;
  };
  const labels = {
    requests: zh ? "请求量" : "Requests",
    tokens: zh ? "Token" : "Tokens",
    cost: zh ? "成本" : "Cost",
    cache: zh ? "Token 缓存命中率" : "Token cache hit rate",
    duration: zh ? "总时长" : "Total duration",
  };
  const rows = isError || isLoading ? [] : (analytics?.items ?? []);
  const sortedRows = [...rows].sort((a, b) => {
    const left = sort.field === "success" ? successRate(a) : a[sort.field];
    const right = sort.field === "success" ? successRate(b) : b[sort.field];
    if (left === null) return right === null ? a.key.localeCompare(b.key) : 1;
    if (right === null) return -1;
    return (
      (sort.ascending ? left - right : right - left) ||
      a.key.localeCompare(b.key)
    );
  });
  const columns: Array<{ field: SortField; label: string }> = [
    { field: "requests", label: labels.requests },
    { field: "success", label: zh ? "成功率" : "Success rate" },
    { field: "cache_hit_rate", label: labels.cache },
    { field: "total_tokens", label: zh ? "Token 用量" : "Total tokens" },
    { field: "total_cost_usd", label: labels.cost },
    { field: "wait_time_ms", label: labels.duration },
  ];
  const logHref = (row: OverviewAttributionItem) =>
    requestLogsHref(timeRange, {
      status: "failed",
      ...(dimension === "model"
        ? {
            model: row.key,
            ...(filterKey !== null ? { channel: filterKey } : {}),
          }
        : {
            channel: row.key,
            ...(filterKey !== null ? { model: filterKey } : {}),
          }),
    });
  const selected = rows.find((row) => row.key === selectedKey);
  const formatValue = (value: number) =>
    metric === "cache"
      ? `${(value * 100).toFixed(1)}%`
      : metric === "cost"
        ? formatMoney(value)
        : metric === "duration"
          ? formatDuration(value, zh)
          : formatCompact(value);
  const points = useMemo(
    () => analytics?.trend.filter((point) => point.key === selectedKey) ?? [],
    [analytics, selectedKey],
  );
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const emptyMessage = isLoading
    ? zh
      ? "正在加载使用数据…"
      : "Loading usage…"
    : isError
      ? zh
        ? "使用数据加载失败，请刷新重试"
        : "Unable to load usage. Refresh to retry."
      : zh
        ? "暂无使用数据"
        : "No usage data";
  const allFilters =
    dimension === "model"
      ? zh
        ? "全部渠道"
        : "All channels"
      : zh
        ? "全部模型"
        : "All models";
  const filters = analytics?.filters ?? [];
  const filter = filters.find((option) => option.key === filterKey);
  const displayLabel = (
    key: string,
    label: string,
    dim: AttributionDimension,
  ) =>
    key
      ? label
      : dim === "model"
        ? zh
          ? "未知模型"
          : "Unknown model"
        : zh
          ? "未知渠道"
          : "Unknown channel";
  return (
    <section className="flex min-w-0 flex-col gap-3">
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-3 px-1">
        <h3 className="text-sm font-semibold">
          {zh ? "模型与渠道" : "Models and channels"}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedControl
            value={dimension}
            onValueChange={(value) => {
              setSelectedKey(null);
              setPage(1);
              onDimensionChange(value);
            }}
            options={[
              { value: "model", label: zh ? "按模型" : "By model" },
              { value: "channel", label: zh ? "按渠道" : "By channel" },
            ]}
          />
          <Popover open={filterOpen} onOpenChange={setFilterOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="max-w-60 text-xs"
                aria-label={zh ? "交叉筛选" : "Cross filter"}
              >
                <span className="truncate">
                  {filterKey === null
                    ? allFilters
                    : (filter?.label ?? analytics?.filter_label ?? filterKey)}
                </span>
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-72 p-1">
              <div className="flex max-h-64 flex-col overflow-y-auto">
                <Button
                  variant="ghost"
                  size="sm"
                  className="justify-start text-xs"
                  onClick={() => {
                    onFilterChange(null);
                    setSelectedKey(null);
                    setPage(1);
                    setFilterOpen(false);
                  }}
                >
                  {allFilters}
                </Button>
                {filters.map((option) => (
                  <Button
                    key={option.key}
                    variant="ghost"
                    size="sm"
                    className="justify-start gap-2 text-xs"
                    onClick={() => {
                      onFilterChange(option.key);
                      setSelectedKey(null);
                      setPage(1);
                      setFilterOpen(false);
                    }}
                  >
                    <span className="truncate">
                      {displayLabel(
                        option.key,
                        option.label,
                        dimension === "model" ? "channel" : "model",
                      )}
                    </span>
                    {option.is_deleted ? (
                      <Badge variant="secondary">
                        {zh ? "已删除" : "Deleted"}
                      </Badge>
                    ) : null}
                    <span className="ml-auto max-w-24 truncate font-mono text-muted-foreground">
                      {option.key.slice(0, 8)}
                    </span>
                  </Button>
                ))}
              </div>
            </PopoverContent>
          </Popover>
        </div>
      </div>
      {!isLoading &&
      !isError &&
      analytics &&
      !analytics.coverage.has_dimension_history ? (
        <p role="status" className="px-1 text-xs text-muted-foreground">
          {zh
            ? "部分旧统计未保存模型和渠道明细，以下仅展示可归因数据。"
            : "Some older statistics lack model and channel details. Only attributable usage is shown."}
        </p>
      ) : null}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>
              {dimension === "model"
                ? zh
                  ? "实际上游模型"
                  : "Upstream model"
                : zh
                  ? "渠道"
                  : "Channel"}
            </TableHead>
            {columns.map((column) => (
              <TableHead
                key={column.field}
                className="text-right"
                aria-sort={
                  sort.field === column.field
                    ? sort.ascending
                      ? "ascending"
                      : "descending"
                    : "none"
                }
              >
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-0 text-xs"
                  onClick={() => {
                    setSort({
                      field: column.field,
                      ascending:
                        sort.field === column.field ? !sort.ascending : false,
                    });
                    setPage(1);
                  }}
                >
                  {column.label}
                  {sort.field === column.field
                    ? sort.ascending
                      ? " ↑"
                      : " ↓"
                    : ""}
                </Button>
              </TableHead>
            ))}
            <TableHead>
              <span className="sr-only">{zh ? "操作" : "Actions"}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length ? (
            sortedRows
              .slice((currentPage - 1) * pageSize, currentPage * pageSize)
              .map((row) => (
                <Fragment key={row.key}>
                  <TableRow
                    data-state={
                      selectedKey === row.key ? "selected" : undefined
                    }
                  >
                    <TableCell className="max-w-64">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="size-5 shrink-0"
                          aria-expanded={expandedKey === row.key}
                          aria-label={`${zh ? "展开明细" : "Toggle details"} ${displayLabel(row.key, row.label, dimension)}`}
                          onClick={() =>
                            setExpandedKey(
                              expandedKey === row.key ? null : row.key,
                            )
                          }
                        >
                          {expandedKey === row.key ? (
                            <ChevronDown className="size-3.5" />
                          ) : (
                            <ChevronRight className="size-3.5" />
                          )}
                        </Button>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-auto max-w-56 justify-start p-0 text-xs font-normal"
                              aria-pressed={selectedKey === row.key}
                              onClick={() =>
                                setSelectedKey(
                                  selectedKey === row.key ? null : row.key,
                                )
                              }
                            >
                              <span className="truncate font-mono">
                                {displayLabel(row.key, row.label, dimension)}
                              </span>
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            {displayLabel(row.key, row.label, dimension)}
                            {dimension === "channel" ? (
                              <div className="font-mono">{row.key}</div>
                            ) : null}
                          </TooltipContent>
                        </Tooltip>
                        {row.is_deleted ? (
                          <Badge variant="secondary">
                            {zh ? "已删除" : "Deleted"}
                          </Badge>
                        ) : null}
                      </div>
                      {dimension === "channel" ? (
                        <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
                          {row.key.slice(0, 8)}
                        </div>
                      ) : null}
                    </TableCell>
                    {[
                      formatCompact(row.requests),
                      successRate(row) === null
                        ? "—"
                        : `${(successRate(row)! * 100).toFixed(1)}%`,
                      row.cache_hit_rate === null
                        ? "—"
                        : `${(row.cache_hit_rate * 100).toFixed(1)}%`,
                      formatCompact(row.total_tokens),
                      formatMoney(row.total_cost_usd),
                      formatDuration(row.wait_time_ms, zh),
                    ].map((value, index) => (
                      <TableCell
                        key={`${index}-${value}`}
                        className="text-right tabular-nums"
                      >
                        {value}
                      </TableCell>
                    ))}
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs"
                        onClick={() => {
                          onDimensionChange(
                            dimension === "model" ? "channel" : "model",
                          );
                          onFilterChange(row.key);
                          setSelectedKey(null);
                          setPage(1);
                        }}
                      >
                        {dimension === "model"
                          ? zh
                            ? "比较渠道"
                            : "Compare channels"
                          : zh
                            ? "比较模型"
                            : "Compare models"}
                      </Button>
                    </TableCell>
                  </TableRow>
                  {expandedKey === row.key ? (
                    <TableRow>
                      <TableCell colSpan={8}>
                        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 py-2">
                          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-4">
                            {[
                              {
                                label: zh ? "输入" : "Input",
                                value: row.input_tokens,
                              },
                              {
                                label: zh ? "输出" : "Output",
                                value: row.output_tokens,
                              },
                              {
                                label: zh ? "缓存读取" : "Cache read",
                                value: row.cache_read_input_tokens,
                              },
                              {
                                label: zh ? "缓存写入" : "Cache write",
                                value: row.cache_write_input_tokens,
                              },
                            ].map((detail) => (
                              <div key={detail.label} className="flex gap-2">
                                <dt className="text-muted-foreground">
                                  {detail.label}
                                </dt>
                                <dd className="tabular-nums">
                                  {formatCompact(detail.value)}
                                </dd>
                              </div>
                            ))}
                          </dl>
                          <span className="text-xs text-muted-foreground">
                            {zh ? "成功" : "Successful"}{" "}
                            {row.successful_requests.toLocaleString()} /{" "}
                            {zh ? "失败" : "Failed"}{" "}
                            {row.failed_requests.toLocaleString()}
                          </span>
                          <Button
                            asChild
                            variant="ghost"
                            size="sm"
                            className="h-6 text-xs"
                          >
                            <Link to={logHref(row)}>
                              {zh ? "查看失败请求" : "View failed requests"}
                            </Link>
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : null}
                </Fragment>
              ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={8}
                className="h-24 text-center text-muted-foreground"
              >
                <span role="status">{emptyMessage}</span>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      {rows.length ? (
        <TablePagination
          locale={locale}
          total={rows.length}
          page={currentPage}
          pageCount={pageCount}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size);
            setPage(1);
          }}
        />
      ) : null}
      {selected ? (
        <div className="rounded-md bg-muted/35 p-3 md:p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="max-w-full truncate font-mono text-xs">
              {displayLabel(selected.key, selected.label, dimension)}
            </span>
            <div className="max-w-full overflow-x-auto">
              <SegmentedControl
                value={metric}
                onValueChange={onMetricChange}
                options={(Object.keys(labels) as AnalysisMetric[]).map(
                  (value) => ({ value, label: labels[value] }),
                )}
              />
            </div>
          </div>
          <ChartContainer
            config={{
              value: { label: labels[metric], color: "var(--chart-4)" },
            }}
            className="mt-3 h-[200px] w-full"
          >
            <LineChart accessibilityLayer data={points}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                tickFormatter={formatTrendLabel}
                tickLine={false}
                axisLine={false}
                minTickGap={24}
              />
              <YAxis
                tickFormatter={formatValue}
                domain={metric === "cache" ? [0, 1] : [0, "auto"]}
                tickLine={false}
                axisLine={false}
              />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    labelFormatter={(value) => formatTrendLabel(String(value))}
                    formatter={(value) => (
                      <span>{formatValue(Number(value))}</span>
                    )}
                  />
                }
              />
              <Line
                dataKey="value"
                stroke="var(--chart-4)"
                strokeWidth={2}
                dot={points.length < 25}
                connectNulls={false}
              />
            </LineChart>
          </ChartContainer>
        </div>
      ) : rows.length ? (
        <p className="px-1 text-xs text-muted-foreground">
          {zh
            ? "点击模型或渠道查看趋势"
            : "Select a model or channel to view its trend"}
        </p>
      ) : null}
    </section>
  );
}
