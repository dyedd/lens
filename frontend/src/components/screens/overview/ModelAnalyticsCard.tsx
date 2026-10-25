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
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/Chart";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import {
  CHART_COLORS,
  formatCompact,
  formatMoney,
  PIE_METRIC_OPTIONS,
  type PieMetric,
} from "./overviewMetrics";

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
  modelTrendTitle: string;
  modelsIsError: boolean;
  pieChartConfig: ChartConfig;
  pieData: { data: PieDatum[]; total: number };
  pieMetric: PieMetric;
  pieMetricLabel: string;
  onMetricChange: (metric: PieMetric) => void;
};

function EmptyBlock({ label }: { label: string }) {
  return (
    <div className="flex min-h-[220px] w-full items-center justify-center rounded-md bg-muted/35 text-sm text-muted-foreground">
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
    modelTrendTitle,
    modelsIsError,
    pieChartConfig,
    pieData,
    pieMetric,
    pieMetricLabel,
    onMetricChange,
  } = props;
  const formatMetric = (value: number) =>
    pieMetric === "cost" ? formatMoney(value) : formatCompact(value);
  const formatTooltipValue = (value: unknown) => formatMetric(Number(value));
  const tooltipFormatter = (value: unknown, name?: string | number) => (
    <div className="flex min-w-44 items-center justify-between gap-8">
      <span className="truncate text-muted-foreground">{name ?? ""}</span>
      <span className="shrink-0 font-medium text-foreground tabular-nums">
        {formatTooltipValue(value)}
      </span>
    </div>
  );
  return (
    <section className="space-y-3 px-1">
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">
          {isChineseLocale ? "模型使用情况" : "Model usage"}
        </h3>
        <SegmentedControl
          value={pieMetric}
          onValueChange={onMetricChange}
          options={PIE_METRIC_OPTIONS.map((option) => ({
            value: option.value,
            label: isChineseLocale ? option.zhLabel : option.enLabel,
          }))}
        />
      </div>
      <div className="grid gap-5 rounded-md bg-muted/35 p-2 md:p-3 lg:grid-cols-[minmax(18rem,0.72fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <div className="mb-3 text-sm font-medium text-foreground">
            {isChineseLocale ? "模型分布" : "Model distribution"}
          </div>
          {pieData.data.length ? (
            <div className="grid gap-3">
              <ChartContainer
                config={pieChartConfig}
                className="mx-auto h-[240px] w-full max-w-[300px]"
              >
                <PieChart>
                  <ChartTooltip
                    content={
                      <ChartTooltipContent
                        nameKey="model"
                        hideLabel
                        formatter={tooltipFormatter}
                      />
                    }
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
                              className="fill-foreground text-lg font-semibold tabular-nums"
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
              <div className="grid max-h-24 grid-cols-2 gap-x-3 gap-y-1 overflow-y-auto pr-1 text-xs text-muted-foreground">
                {pieData.data.map((item, index) => (
                  <Tooltip key={`${item.model}-${index}`}>
                    <TooltipTrigger asChild>
                      <div className="flex min-w-0 items-center gap-1.5">
                        <span
                          className="size-2 shrink-0 rounded-[2px]"
                          style={{
                            backgroundColor:
                              CHART_COLORS[index % CHART_COLORS.length],
                          }}
                        />
                        <span className="truncate">{item.model}</span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-sm break-all">
                      {item.model}
                    </TooltipContent>
                  </Tooltip>
                ))}
              </div>
            </div>
          ) : modelsIsError ? null : (
            <EmptyBlock
              label={
                isChineseLocale ? "暂无模型使用数据" : "No model usage data"
              }
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
                <ChartTooltip
                  content={<ChartTooltipContent formatter={tooltipFormatter} />}
                />
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
              label={
                isChineseLocale ? "暂无使用趋势数据" : "No usage trend data"
              }
            />
          )}
        </div>
      </div>
    </section>
  );
}
