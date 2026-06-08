"use client";

import { Button } from "@/components/ui/button";
import { ProtocolMultiSelect } from "@/components/ui/protocol-multi-select";
import type { ProtocolKind } from "@/lib/api";
import type { AggregatedModel } from "./model-aggregation";
import type { Locale } from "./shared";

export function SiteModelAggregateView({
  models,
  locale,
  onChangeModelProtocols,
  onOpenModelTest,
  canTestModel,
  testingDisabled,
}: {
  models: AggregatedModel[];
  locale: Locale;
  onChangeModelProtocols?: (
    modelKey: string,
    nextProtocols: ProtocolKind[],
  ) => void;
  onOpenModelTest?: (modelKey: string) => void;
  canTestModel?: (modelKey: string) => boolean;
  testingDisabled?: boolean;
}) {
  if (!models.length) {
    return (
      <div className="py-4 text-sm text-muted-foreground">
        {locale === "zh-CN"
          ? "暂无模型，请先添加或获取模型"
          : "No models yet. Add or fetch models first."}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      {models.map(({ key: modelKey, modelName, protocols, sources }) => {
        const testable = Boolean(canTestModel?.(modelKey));
        return (
          <div
            key={modelKey}
            className="flex min-w-0 flex-wrap items-center gap-3 rounded-md border bg-background px-3 py-2"
          >
            <span className="min-w-0 flex-1 truncate text-sm font-medium">
              {modelName}
            </span>
            <ProtocolMultiSelect
              value={protocols}
              onChange={(next) => onChangeModelProtocols?.(modelKey, next)}
              locale={locale}
              className="w-auto min-w-[180px]"
              invalid={protocols.length === 0}
              requireAtLeastOne
            />
            <span className="text-xs text-muted-foreground">
              {sources.join(", ")}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 px-2 text-muted-foreground hover:text-foreground"
              onClick={() => onOpenModelTest?.(modelKey)}
              disabled={!testable || testingDisabled}
            >
              {locale === "zh-CN" ? "测试" : "Test"}
            </Button>
          </div>
        );
      })}
    </div>
  );
}
