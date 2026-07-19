"use client";

import { useMemo, useState } from "react";
import { FolderPlus, RefreshCcw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import type { ProtocolKind } from "@/lib/api";
import { SiteModelAggregateView } from "./SiteModelAggregateView";
import type { AggregatedModel } from "./useAggregatedModels";
import type {
  BatchModelTestOption,
  Locale,
  TestableModelOption,
} from "./channelShared";

type Props = {
  locale: Locale;
  overviewModels: AggregatedModel[];
  modelTestOptionByKey: Map<string, TestableModelOption>;
  batchTestOptions: BatchModelTestOption[];
  isBatchModelTestRunning: boolean;
  testingModel: boolean;
  isEnsuringModelGroups: boolean;
  onEnsureModelGroups: () => void;
  onOpenBatchTest: () => void;
  onUpdateModelProtocols: (modelKey: string, protocols: ProtocolKind[]) => void;
  onOpenModelTest: (modelKey: string) => void;
  onRemoveModel: (modelKey: string) => void;
  onClearModels: () => void;
};

/** Renders aggregate channel models and their bulk actions. */
export function ChannelModelOverviewSection({
  locale,
  overviewModels,
  modelTestOptionByKey,
  batchTestOptions,
  isBatchModelTestRunning,
  testingModel,
  isEnsuringModelGroups,
  onEnsureModelGroups,
  onOpenBatchTest,
  onUpdateModelProtocols,
  onOpenModelTest,
  onRemoveModel,
  onClearModels,
}: Props) {
  const [search, setSearch] = useState("");
  const normalizedSearch = search.trim().toLowerCase();
  const filteredModels = useMemo(() => {
    if (!normalizedSearch) return overviewModels;
    return overviewModels.filter(
      (model) =>
        model.modelName.toLowerCase().includes(normalizedSearch) ||
        model.sources.some((source) =>
          source.toLowerCase().includes(normalizedSearch),
        ),
    );
  }, [normalizedSearch, overviewModels]);
  const hasSearch = normalizedSearch.length > 0;

  return (
    <div className="mt-4">
      <div className="mb-2 flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-center">
          <div className="shrink-0 text-base font-semibold text-foreground">
            {locale === "zh-CN" ? "模型总览" : "Model Overview"}
          </div>
          {overviewModels.length ? (
            <>
              <ToolbarSearchInput
                value={search}
                onChange={setSearch}
                onClear={() => setSearch("")}
                placeholder={
                  locale === "zh-CN"
                    ? "搜索模型或来源"
                    : "Search models or sources"
                }
                className="max-w-none sm:max-w-sm"
              />
              <div className="shrink-0 text-xs text-muted-foreground">
                {hasSearch
                  ? locale === "zh-CN"
                    ? `找到 ${filteredModels.length}/${overviewModels.length} 个模型`
                    : `${filteredModels.length}/${overviewModels.length} matched`
                  : locale === "zh-CN"
                    ? `共 ${overviewModels.length} 个模型`
                    : `${overviewModels.length} models`}
              </div>
            </>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-destructive"
            onClick={onClearModels}
            disabled={!overviewModels.length}
          >
            <Trash2 data-icon="inline-start" />
            {locale === "zh-CN" ? "清空" : "Clear"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onEnsureModelGroups}
            disabled={
              !overviewModels.length ||
              isEnsuringModelGroups ||
              isBatchModelTestRunning ||
              testingModel
            }
          >
            {isEnsuringModelGroups ? (
              <RefreshCcw data-icon="inline-start" className="animate-spin" />
            ) : (
              <FolderPlus data-icon="inline-start" />
            )}
            {locale === "zh-CN"
              ? isEnsuringModelGroups
                ? "生成预览中..."
                : "加入/创建模型组"
              : isEnsuringModelGroups
                ? "Preparing preview..."
                : "Add/create groups"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onOpenBatchTest}
            disabled={
              !batchTestOptions.length ||
              isBatchModelTestRunning ||
              testingModel
            }
          >
            <RefreshCcw
              data-icon="inline-start"
              className={isBatchModelTestRunning ? "animate-spin" : undefined}
            />
            {locale === "zh-CN" ? "批量测试" : "Batch test"}
          </Button>
        </div>
      </div>
      <SiteModelAggregateView
        models={filteredModels}
        locale={locale}
        emptyLabel={
          hasSearch
            ? locale === "zh-CN"
              ? "没有匹配的模型"
              : "No matching models"
            : undefined
        }
        onChangeModelProtocols={onUpdateModelProtocols}
        onOpenModelTest={onOpenModelTest}
        onRemoveModel={onRemoveModel}
        canTestModel={(modelKey) => modelTestOptionByKey.has(modelKey)}
        testingDisabled={testingModel || isBatchModelTestRunning}
      />
    </div>
  );
}
