import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Label,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/Chart";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import {
  CHART_COLORS,
  formatCompact,
  formatMoney,
  PIE_METRIC_OPTIONS,
  TIME_RANGE_OPTIONS,
  type PieMetric,
  type TimeRange,
} from "./overviewUtils";

type PieDatum = {
  model: string;
  value: number;
  requests: number;
  total_cost_usd: number;
};
type Props = {
  barConfig: ChartConfig;
  barData: Array<Record<string, number | string>>;
  barModels: string[];
  isChineseLocale: boolean;
  modelCardDescription: string;
  modelRange: TimeRange;
  modelTrendTitle: string;
  modelsIsError: boolean;
  pieChartConfig: ChartConfig;
  pieData: { data: PieDatum[]; total: number };
  pieMetric: PieMetric;
  pieMetricLabel: string;
  onMetricChange: (metric: PieMetric) => void;
  onRangeChange: (range: TimeRange) => void;
};

function EmptyBlock({ label }: { label: string }) {
  return (
    <div className="flex min-h-[260px] w-full items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
      {label}
    </div>
  );
}

/** Render model distribution and trend analytics. */
export function ModelAnalyticsCard(props: Props) {
  const {
    barConfig,
    barData,
    barModels,
    isChineseLocale,
    modelCardDescription,
    modelRange,
    modelTrendTitle,
    modelsIsError,
    pieChartConfig,
    pieData,
    pieMetric,
    pieMetricLabel,
    onMetricChange,
    onRangeChange,
  } = props;
  const formatMetric = (value: number) =>
    pieMetric === "cost" ? formatMoney(value) : formatCompact(value);
  return (
    <Card size="sm" className="py-0">
      <CardHeader className="flex flex-col items-start justify-between gap-3 border-b py-4 lg:flex-row lg:items-center">
        <div className="min-w-0">
          <CardTitle className="text-base">
            {isChineseLocale ? "模型分析" : "Model analytics"}
          </CardTitle>
          <CardDescription>{modelCardDescription}</CardDescription>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Select
            value={pieMetric}
            onValueChange={(value) => onMetricChange(value as PieMetric)}
          >
            <SelectTrigger
              className="w-full sm:w-32"
              aria-label={
                isChineseLocale ? "选择模型占比指标" : "Select model metric"
              }
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end" className="rounded-xl">
              {PIE_METRIC_OPTIONS.map((option) => (
                <SelectItem
                  key={option.value}
                  value={option.value}
                  className="rounded-lg"
                >
                  {isChineseLocale ? option.zhLabel : option.enLabel}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={modelRange}
            onValueChange={(value) => onRangeChange(value as TimeRange)}
          >
            <SelectTrigger
              className="w-full sm:w-36"
              aria-label={
                isChineseLocale ? "选择模型统计范围" : "Select model range"
              }
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end" className="rounded-xl">
              {TIME_RANGE_OPTIONS.map((option) => (
                <SelectItem
                  key={option.value}
                  value={option.value}
                  className="rounded-lg"
                >
                  {isChineseLocale ? option.zhLabel : option.enLabel}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="grid gap-5 p-4 lg:grid-cols-[minmax(18rem,0.72fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <div className="mb-3 text-sm font-medium text-foreground">
            {isChineseLocale ? "模型组合" : "Model mix"}
          </div>
          {pieData.data.length ? (
            <div className="grid gap-3">
              <ChartContainer
                config={pieChartConfig}
                className="mx-auto h-[240px] w-full max-w-[300px]"
              >
                <PieChart>
                  <ChartTooltip
                    content={<ChartTooltipContent nameKey="model" hideLabel />}
                  />
                  <Pie
                    data={pieData.data}
                    dataKey="value"
                    nameKey="model"
                    innerRadius={58}
                    outerRadius={96}
                    paddingAngle={2}
                  >
                    <Label
                      content={({ viewBox }) => {
                        if (
                          !viewBox ||
                          !("cx" in viewBox) ||
                          !("cy" in viewBox)
                        )
                          return null;
                        return (
                          <text
                            x={viewBox.cx}
                            y={viewBox.cy}
                            textAnchor="middle"
                            dominantBaseline="middle"
                          >
                            <tspan
                              x={viewBox.cx}
                              y={viewBox.cy}
                              className="brand-times-italic fill-foreground text-xl font-semibold tabular-nums"
                            >
                              {formatMetric(pieData.total)}
                            </tspan>
                            <tspan
                              x={viewBox.cx}
                              y={(viewBox.cy || 0) + 20}
                              className="fill-muted-foreground text-xs"
                            >
                              {pieMetricLabel}
                            </tspan>
                          </text>
                        );
                      }}
                    />
                    {pieData.data.map((_, index) => (
                      <Cell
                        key={index}
                        fill={CHART_COLORS[index % CHART_COLORS.length]}
                      />
                    ))}
                  </Pie>
                </PieChart>
              </ChartContainer>
              <div className="grid max-h-24 grid-cols-2 gap-x-3 gap-y-1 overflow-y-auto pr-1 text-[11px] text-muted-foreground">
                {pieData.data.map((item, index) => (
                  <div
                    key={`${item.model}-${index}`}
                    className="flex min-w-0 items-center gap-1.5"
                    title={item.model}
                  >
                    <span
                      className="size-2 shrink-0 rounded-[2px]"
                      style={{
                        backgroundColor:
                          CHART_COLORS[index % CHART_COLORS.length],
                      }}
                    />
                    <span className="truncate">{item.model}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : modelsIsError ? null : (
            <EmptyBlock
              label={isChineseLocale ? "暂无模型占比数据" : "No model mix data"}
            />
          )}
        </div>
        <div className="min-w-0 lg:border-l lg:pl-5">
          <div className="mb-3 text-sm font-medium text-foreground">
            {modelTrendTitle}
          </div>
          {barData.length ? (
            <ChartContainer
              config={barConfig}
              className="h-[260px] w-full sm:h-[320px]"
            >
              <BarChart
                accessibilityLayer
                data={barData}
                margin={{ left: 8, right: 8 }}
              >
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={false}
                  fontSize={11}
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  fontSize={11}
                  tickFormatter={formatMetric}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                <ChartLegend
                  content={
                    <ChartLegendContent className="flex-wrap justify-start gap-x-3 gap-y-2 pb-3" />
                  }
                />
                {barModels.map((key) => (
                  <Bar
                    key={key}
                    dataKey={key}
                    stackId="a"
                    fill={barConfig[key]?.color}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            </ChartContainer>
          ) : modelsIsError ? null : (
            <EmptyBlock
              label={isChineseLocale ? "暂无消耗趋势数据" : "No trend data"}
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}
