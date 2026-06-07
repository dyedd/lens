"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { ProtocolMultiSelect } from "@/components/ui/protocol-multi-select";
import type { ProtocolKind } from "@/lib/api";
import type { AggregatedModel } from "./model-aggregation";
import {
  allClientProtocols,
  type FormProtocolConfig,
  genericModelKey,
  type Locale,
} from "./shared";

export function SiteModelAggregateView({
  models,
  protocolConfigs,
  locale,
  onChangeModelProtocols,
  onOpenModelTest,
  canTestModel,
  testingDisabled,
}: {
  models: AggregatedModel[];
  protocolConfigs: FormProtocolConfig[];
  locale: Locale;
  onChangeModelProtocols?: (
    credentialId: string,
    modelName: string,
    nextProtocols: ProtocolKind[],
  ) => void;
  onOpenModelTest?: (credentialId: string, modelName: string) => void;
  canTestModel?: (credentialId: string, modelName: string) => boolean;
  testingDisabled?: boolean;
}) {
  const allowedProtocolsMap = useMemo(() => {
    const map: Record<string, Set<ProtocolKind>> = {};
    protocolConfigs.forEach((protocolConfig) => {
      if (!protocolConfig.enabled) return;
      protocolConfig.models.forEach((model) => {
        const key = genericModelKey(model);
        if (!map[key]) map[key] = new Set();
        allClientProtocols.forEach((p) => map[key].add(p));
      });
    });
    return map;
  }, [protocolConfigs]);
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
      {models.map(({ credentialId, modelName, protocols, sources }) => {
        const modelKey = genericModelKey({
          credential_id: credentialId,
          model_name: modelName,
        });
        const allowed = Array.from(allowedProtocolsMap[modelKey] ?? []);
        const testable = Boolean(canTestModel?.(credentialId, modelName));
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
              allowedProtocols={allowed}
              onChange={(next) =>
                onChangeModelProtocols?.(credentialId, modelName, next)
              }
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
              onClick={() => onOpenModelTest?.(credentialId, modelName)}
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
