"use client";

import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ProtocolMultiSelect } from "@/components/ui/ProtocolMultiSelect";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { ProtocolKind } from "@/lib/api";
import type { Locale } from "./channelShared";
import type { AggregatedModel } from "./useAggregatedModels";

/** Renders aggregated channel models with protocol and test actions. */
export function SiteModelAggregateView({
  models,
  locale,
  emptyLabel,
  onChangeModelProtocols,
  onChangeModelSource,
  onOpenModelTest,
  onRemoveModel,
  canTestModel,
  testingDisabled,
}: {
  models: AggregatedModel[];
  locale: Locale;
  emptyLabel?: string;
  onChangeModelProtocols: (
    modelKey: string,
    nextProtocols: ProtocolKind[],
  ) => void;
  onChangeModelSource: (
    modelKey: string,
    source: AggregatedModel["source"],
  ) => void;
  onOpenModelTest: (modelKey: string) => void;
  onRemoveModel: (modelKey: string) => void;
  canTestModel: (modelKey: string) => boolean;
  testingDisabled: boolean;
}) {
  if (!models.length) {
    return (
      <div className="py-4 text-sm text-muted-foreground">
        {emptyLabel ||
          (locale === "zh-CN"
            ? "暂无模型，请先添加或获取模型"
            : "No models yet. Add or fetch models first.")}
      </div>
    );
  }
  const sourceOptions: Array<{
    value: AggregatedModel["source"];
    label: string;
  }> = [
    { value: "manual", label: locale === "zh-CN" ? "手动" : "Manual" },
    { value: "synced", label: locale === "zh-CN" ? "同步" : "Synced" },
  ];
  return (
    <div className="grid min-w-0 max-h-[min(52dvh,28rem)] overflow-y-auto">
      {models.map(
        ({ key: modelKey, modelName, protocols, sourceLabel, source }) => {
          const testable = canTestModel(modelKey);
          return (
            <div
              key={modelKey}
              className="grid min-w-0 gap-2 border-b py-1 last:border-b-0 md:grid-cols-[minmax(0,1fr)_minmax(180px,0.34fr)_minmax(200px,0.42fr)_auto] md:items-center"
            >
              <div className="min-w-0">
                <div className="flex min-w-0 items-center gap-2">
                  <div className="truncate text-sm font-medium">
                    {modelName}
                  </div>
                  <SegmentedControl
                    value={source}
                    onValueChange={(nextSource) =>
                      onChangeModelSource(modelKey, nextSource)
                    }
                    options={sourceOptions}
                    className="shrink-0"
                  />
                </div>
                <div className="truncate text-xs text-muted-foreground md:hidden">
                  {sourceLabel}
                </div>
              </div>
              <ProtocolMultiSelect
                value={protocols}
                onChange={(next) => onChangeModelProtocols(modelKey, next)}
                locale={locale}
                invalid={protocols.length === 0}
                shouldRequireAtLeastOne
              />
              <span className="hidden truncate text-xs text-muted-foreground md:block">
                {sourceLabel}
              </span>
              <div className="flex items-center justify-end gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2 text-muted-foreground hover:text-foreground"
                  onClick={() => onOpenModelTest(modelKey)}
                  disabled={!testable || testingDisabled}
                >
                  {locale === "zh-CN" ? "测试" : "Test"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-destructive"
                  aria-label={locale === "zh-CN" ? "删除模型" : "Delete model"}
                  title={locale === "zh-CN" ? "删除模型" : "Delete model"}
                  onClick={() => onRemoveModel(modelKey)}
                >
                  <Trash2 />
                </Button>
              </div>
            </div>
          );
        },
      )}
    </div>
  );
}
