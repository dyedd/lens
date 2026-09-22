import {
  Activity,
  Archive,
  ArrowDownToLine,
  ArrowUpFromLine,
  Braces,
  CircleCheck,
  Database,
  DollarSign,
  HardDrive,
  Timer,
} from "lucide-react";
import { OverviewStatCard } from "./OverviewStatCard";
import { formatCompact, formatDuration, formatMoney } from "./overviewMetrics";

type Props = {
  cacheReadTokens: number;
  cacheWriteTokens: number;
  consumedTime: number;
  inputCost: number;
  inputTokens: number;
  isChineseLocale: boolean;
  outputCost: number;
  outputTokens: number;
  requestCount: number;
  successRate: number;
  totalCost: number;
  totalTokens: number;
};

/** Render the four overview summary metrics. */
export function OverviewStats(props: Props) {
  const {
    cacheReadTokens,
    cacheWriteTokens,
    consumedTime,
    inputCost,
    inputTokens,
    isChineseLocale,
    outputCost,
    outputTokens,
    requestCount,
    successRate,
    totalCost,
    totalTokens,
  } = props;
  const cycleLabel = isChineseLocale
    ? "点击切换指标"
    : "Click to switch metric";

  return (
    <section className="space-y-3">
      <h3 className="px-1 text-sm font-semibold">
        {isChineseLocale ? "用量统计" : "Usage"}
      </h3>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <OverviewStatCard
          cycleLabel={cycleLabel}
          views={[
            {
              icon: Activity,
              title: isChineseLocale ? "请求总量" : "Total requests",
              value: formatCompact(requestCount),
            },
            {
              icon: CircleCheck,
              title: isChineseLocale ? "成功率" : "Success rate",
              value: `${successRate}%`,
            },
            {
              icon: Timer,
              title: isChineseLocale ? "消耗时间" : "Time spent",
              value: formatDuration(consumedTime),
            },
          ]}
        />
        <OverviewStatCard
          cycleLabel={cycleLabel}
          views={[
            {
              icon: DollarSign,
              title: isChineseLocale ? "总费用" : "Total spend",
              value: formatMoney(totalCost),
            },
            {
              icon: ArrowDownToLine,
              title: isChineseLocale ? "输入费用" : "Input spend",
              value: formatMoney(inputCost),
            },
            {
              icon: ArrowUpFromLine,
              title: isChineseLocale ? "输出费用" : "Output spend",
              value: formatMoney(outputCost),
            },
          ]}
        />
        <OverviewStatCard
          cycleLabel={cycleLabel}
          views={[
            {
              icon: Braces,
              title: isChineseLocale ? "总 Tokens" : "Total tokens",
              value: formatCompact(totalTokens),
            },
            {
              icon: ArrowDownToLine,
              title: isChineseLocale ? "输入 Tokens" : "Input tokens",
              value: formatCompact(inputTokens),
            },
            {
              icon: ArrowUpFromLine,
              title: isChineseLocale ? "输出 Tokens" : "Output tokens",
              value: formatCompact(outputTokens),
            },
          ]}
        />
        <OverviewStatCard
          cycleLabel={cycleLabel}
          views={[
            {
              icon: Database,
              title: isChineseLocale ? "缓存 Tokens" : "Cache tokens",
              value: formatCompact(cacheReadTokens + cacheWriteTokens),
            },
            {
              icon: Archive,
              title: isChineseLocale ? "缓存读取" : "Cache read",
              value: formatCompact(cacheReadTokens),
            },
            {
              icon: HardDrive,
              title: isChineseLocale ? "缓存写入" : "Cache write",
              value: formatCompact(cacheWriteTokens),
            },
          ]}
        />
      </div>
    </section>
  );
}
