import {
  Activity,
  ArrowDownToLine,
  ArrowUpFromLine,
  DollarSign,
} from "lucide-react";
import { OverviewStatCard } from "./OverviewStatCard";
import {
  formatCompact,
  formatDuration,
  formatMoney,
  type StatTrendPoint,
} from "./overviewUtils";

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
  statTrends: {
    requests: StatTrendPoint[];
    cost: StatTrendPoint[];
    inputTokens: StatTrendPoint[];
    outputTokens: StatTrendPoint[];
  };
  successRate: number;
  totalCost: number;
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
    statTrends,
    successRate,
    totalCost,
  } = props;
  return (
    <section>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <OverviewStatCard
          icon={Activity}
          title={isChineseLocale ? "请求总量" : "Total requests"}
          value={formatCompact(requestCount)}
          valueMeta={
            <>
              <span className="brand-times-italic tabular-nums">
                {successRate}%
              </span>{" "}
              {isChineseLocale ? "成功率" : "success rate"}
            </>
          }
          description={`${isChineseLocale ? "消耗时间" : "Time spent"} ${formatDuration(consumedTime)}`}
          trend={statTrends.requests}
          gradientId="overview-requests-trend"
        />
        <OverviewStatCard
          icon={DollarSign}
          title={isChineseLocale ? "总费用" : "Total spend"}
          value={formatMoney(totalCost)}
          description={`${isChineseLocale ? "输入" : "Input"} ${formatMoney(inputCost)} + ${isChineseLocale ? "输出" : "Output"} ${formatMoney(outputCost)}`}
          trend={statTrends.cost}
          gradientId="overview-cost-trend"
        />
        <OverviewStatCard
          icon={ArrowDownToLine}
          title={isChineseLocale ? "输入 Tokens" : "Input tokens"}
          value={formatCompact(inputTokens)}
          description={`${isChineseLocale ? "缓存读取" : "Cache read"} ${formatCompact(cacheReadTokens)}`}
          trend={statTrends.inputTokens}
          gradientId="overview-input-token-trend"
        />
        <OverviewStatCard
          icon={ArrowUpFromLine}
          title={isChineseLocale ? "输出 Tokens" : "Output tokens"}
          value={formatCompact(outputTokens)}
          description={`${isChineseLocale ? "缓存写入" : "Cache write"} ${formatCompact(cacheWriteTokens)}`}
          trend={statTrends.outputTokens}
          gradientId="overview-output-token-trend"
        />
      </div>
    </section>
  );
}
