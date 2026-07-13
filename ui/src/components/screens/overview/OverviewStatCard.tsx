import type { ComponentType, ReactNode } from "react";
import { Area, AreaChart, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { ChartContainer } from "@/components/ui/Chart";
import type { StatTrendPoint } from "./overviewUtils";

type Props = {
  icon: ComponentType<{ className?: string }>;
  title: string;
  value: string;
  valueMeta?: ReactNode;
  description: string;
  trend: StatTrendPoint[];
  gradientId: string;
};

/** Render one overview metric with its compact trend chart. */
export function OverviewStatCard({
  icon: Icon,
  title,
  value,
  valueMeta,
  description,
  trend,
  gradientId,
}: Props) {
  return (
    <Card size="sm" className="overflow-hidden py-0">
      <CardHeader className="flex flex-row items-start justify-between gap-3 px-5 pt-5 pb-0">
        <CardTitle className="truncate text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <span
          aria-hidden="true"
          className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/[0.08] text-primary"
        >
          <Icon className="size-4" />
        </span>
      </CardHeader>
      <CardContent className="grid min-h-[148px] grid-cols-[minmax(0,1fr)_38%] grid-rows-[1fr_auto] items-end gap-x-3 gap-y-3 px-5 pt-2 pb-5">
        <div className="min-w-0 self-center">
          <div className="flex min-w-0 flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
            <div className="brand-times-italic shrink-0 text-3xl font-semibold tracking-normal text-foreground tabular-nums">
              {value}
            </div>
            {valueMeta ? (
              <div className="min-w-0 text-xs font-medium text-muted-foreground tabular-nums sm:text-sm">
                {valueMeta}
              </div>
            ) : null}
          </div>
        </div>
        <div className="h-20 min-w-0 self-center">
          <ChartContainer
            config={{ value: { label: title, color: "var(--primary)" } }}
            className="h-full w-full aspect-auto"
            initialDimension={{ width: 160, height: 80 }}
          >
            <AreaChart
              accessibilityLayer
              data={trend}
              margin={{ top: 8, right: 0, left: 0, bottom: 4 }}
            >
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--color-value)"
                    stopOpacity={0.3}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--color-value)"
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <YAxis
                hide
                domain={[0, (dataMax: number) => Math.max(dataMax, 1)]}
              />
              <Area
                type="natural"
                dataKey="value"
                stroke="var(--color-value)"
                strokeWidth={2.5}
                fill={`url(#${gradientId})`}
                fillOpacity={1}
                dot={false}
                activeDot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ChartContainer>
        </div>
        <div className="col-span-2 min-w-0 truncate text-sm text-muted-foreground tabular-nums">
          {description}
        </div>
      </CardContent>
    </Card>
  );
}
