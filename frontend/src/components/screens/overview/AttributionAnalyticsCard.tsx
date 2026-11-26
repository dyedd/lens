import { ChevronDown, ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";
import { Link } from "react-router";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
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
import { TruncatedTooltip } from "@/components/ui/Tooltip";
import type {
  AttributionDimension,
  OverviewAttribution,
  OverviewAttributionItem,
} from "@/lib/api/overview";
import { cn } from "@/lib/classNames";
import type { Locale } from "@/lib/I18nContext";
import {
  AttributionIcon,
  formatAttributionDisplayLabel,
} from "./AttributionIcon";
import { AttributionVisualGrid } from "./AttributionVisualGrid";
import {
  type AnalysisMetric,
  formatCompact,
  formatDuration,
  formatMoney,
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

type SortField =
  | "requests"
  | "success"
  | "cache_hit_rate"
  | "total_tokens"
  | "total_cost_usd"
  | "wait_time_ms";

export function AttributionAnalyticsCard({
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
  const [sort, setSort] = useState<{ field: SortField; ascending: boolean }>({
    field: "requests",
    ascending: false,
  });

  const successRate = (row: OverviewAttributionItem) => {
    const completed = row.successful_requests + row.failed_requests;
    return completed ? row.successful_requests / completed : null;
  };

  const labels: Record<AnalysisMetric, string> = {
    requests: zh ? "请求" : "Requests",
    tokens: "Token",
    cost: zh ? "成本" : "Cost",
    duration: zh ? "总时长" : "Duration",
    cache: zh ? "缓存" : "Cache",
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
    { field: "requests", label: zh ? "请求量" : "Requests" },
    { field: "success", label: zh ? "成功率" : "Success rate" },
    { field: "cache_hit_rate", label: zh ? "缓存命中率" : "Cache hit rate" },
    { field: "total_tokens", label: zh ? "Token 用量" : "Total tokens" },
    { field: "total_cost_usd", label: zh ? "成本" : "Cost" },
    { field: "wait_time_ms", label: zh ? "总时长" : "Total duration" },
  ];

  const logHref = (row: OverviewAttributionItem) =>
    requestLogsHref(timeRange, {
      status: "failed",
      ...(dimension === "model"
        ? {
            model: row.key,
            ...(filterKey !== null ? { channel: filterKey } : {}),
          }
        : dimension === "channel"
          ? {
              channel: row.key,
              ...(filterKey !== null ? { model: filterKey } : {}),
            }
          : {
              agent: row.key,
              ...(filterKey !== null ? { model: filterKey } : {}),
            }),
    });

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

  return (
    <section className="flex min-w-0 flex-col gap-4">
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-3">
        <h3 className="page-section-title">
          {zh ? "模型、渠道与客户端" : "Models, channels, and clients"}
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
              { value: "model", label: zh ? "模型" : "Models" },
              { value: "channel", label: zh ? "渠道" : "Channels" },
              { value: "agent", label: zh ? "客户端" : "Clients" },
            ]}
          />
          <SegmentedControl
            value={metric}
            onValueChange={onMetricChange}
            options={[
              { value: "tokens", label: labels.tokens },
              { value: "requests", label: labels.requests },
              { value: "cost", label: labels.cost },
              { value: "duration", label: labels.duration },
              { value: "cache", label: labels.cache },
            ]}
          />
          <Popover open={filterOpen} onOpenChange={setFilterOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 max-w-60 text-[13px]"
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
                  className="justify-start text-[13px]"
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
                    className="justify-start gap-2 text-[13px]"
                    onClick={() => {
                      onFilterChange(option.key);
                      setSelectedKey(null);
                      setPage(1);
                      setFilterOpen(false);
                    }}
                  >
                    <span className="truncate">
                      {formatAttributionDisplayLabel(
                        option.key,
                        option.label,
                        dimension === "model" ? "channel" : "model",
                        zh,
                      )}
                    </span>
                    {option.is_deleted ? (
                      <Badge variant="secondary">
                        {zh ? "已删除" : "Deleted"}
                      </Badge>
                    ) : null}
                    <span className="ml-auto max-w-24 truncate font-mono text-xs text-muted-foreground">
                      {option.key.slice(0, 8)}
                    </span>
                  </Button>
                ))}
              </div>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      <div className="space-y-4">
        {rows.length > 0 ? (
          <AttributionVisualGrid
            items={rows}
            trend={analytics?.trend ?? []}
            dimension={dimension}
            metric={metric}
            metricLabel={labels[metric]}
            selectedKey={selectedKey}
            onSelectKey={setSelectedKey}
            zh={zh}
          />
        ) : null}

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                {dimension === "model"
                  ? zh
                    ? "实际上游模型"
                    : "Upstream model"
                  : dimension === "channel"
                    ? zh
                      ? "渠道"
                      : "Channel"
                    : zh
                      ? "客户端 / Agent"
                      : "Client / Agent"}
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
                .map((row) => {
                  const rowLabel = formatAttributionDisplayLabel(
                    row.key,
                    row.label,
                    dimension,
                    zh,
                  );
                  return (
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
                              className={cn(
                                "size-5 shrink-0",
                                expandedKey !== row.key && "intent-reveal",
                              )}
                              aria-expanded={expandedKey === row.key}
                              aria-label={`${zh ? "展开明细" : "Toggle details"} ${rowLabel}`}
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
                            <AttributionIcon
                              dimension={dimension}
                              itemKey={row.key}
                              size={16}
                            />
                            <TruncatedTooltip content={rowLabel}>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-auto max-w-52 justify-start p-0 text-[13px] font-medium"
                                aria-pressed={selectedKey === row.key}
                                onClick={() =>
                                  setSelectedKey(
                                    selectedKey === row.key ? null : row.key,
                                  )
                                }
                              >
                                <span className="truncate">{rowLabel}</span>
                              </Button>
                            </TruncatedTooltip>
                            {row.is_deleted ? (
                              <Badge variant="secondary">
                                {zh ? "已删除" : "Deleted"}
                              </Badge>
                            ) : null}
                          </div>
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
                          {dimension === "agent" ? null : (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="intent-reveal h-6 text-xs"
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
                          )}
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
                                  <div
                                    key={detail.label}
                                    className="flex gap-2"
                                  >
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
                  );
                })
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
      </div>
    </section>
  );
}
