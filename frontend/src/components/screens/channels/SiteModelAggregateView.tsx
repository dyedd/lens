import { ChevronDown, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ProtocolMultiSelect } from "@/components/ui/ProtocolMultiSelect";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { ProtocolKind } from "@/lib/api/protocols";
import { cn } from "@/lib/classNames";
import type { Locale } from "./channelTypes";
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
  const [expandedModelKeys, setExpandedModelKeys] = useState<string[]>([]);
  const toggleExpanded = (modelKey: string) => {
    setExpandedModelKeys((current) =>
      current.includes(modelKey)
        ? current.filter((key) => key !== modelKey)
        : [...current, modelKey],
    );
  };
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
  const pendingLabel = locale === "zh-CN" ? "待上游恢复" : "Awaiting upstream";
  const deleteTargetLabel =
    locale === "zh-CN" ? "删除同步目标" : "Remove sync target";
  const deleteModelLabel = locale === "zh-CN" ? "删除模型" : "Delete model";
  return (
    <div className="grid min-w-0 max-h-[min(52dvh,28rem)] overflow-y-auto">
      {models.map(
        ({
          key: modelKey,
          testKey,
          modelName,
          protocols,
          sourceLabel,
          source,
          members,
        }) => {
          const isTargetOnly = members.every((member) => member.isTargetOnly);
          const testable = testKey !== null && canTestModel(testKey);
          const deleteLabel = isTargetOnly
            ? deleteTargetLabel
            : deleteModelLabel;
          const isExpanded = expandedModelKeys.includes(modelKey);
          const isMultiKey = members.length > 1;
          return (
            <div key={modelKey} className="border-b py-1 last:border-b-0">
              <div className="grid min-w-0 gap-2 md:grid-cols-[minmax(0,1fr)_minmax(180px,0.34fr)_minmax(200px,0.42fr)_auto] md:items-center">
                <div className="min-w-0">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className="truncate text-sm font-medium">
                      {modelName}
                    </div>
                    {isMultiKey ? (
                      <button
                        type="button"
                        className="flex shrink-0 items-center gap-0.5 rounded px-1 py-0.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
                        title={sourceLabel}
                        aria-label={
                          locale === "zh-CN"
                            ? "展开密钥明细"
                            : "Expand key details"
                        }
                        onClick={() => toggleExpanded(modelKey)}
                      >
                        {locale === "zh-CN"
                          ? `${members.length} 个密钥`
                          : `${members.length} keys`}
                        <ChevronDown
                          className={cn(
                            "size-3 transition-transform",
                            isExpanded && "rotate-180",
                          )}
                        />
                      </button>
                    ) : null}
                    {isTargetOnly ? (
                      <span className="shrink-0 rounded-full border border-amber-500/40 px-2 py-1 text-xs font-medium text-amber-700 dark:text-amber-300">
                        {pendingLabel}
                      </span>
                    ) : (
                      <SegmentedControl
                        value={source}
                        onValueChange={(nextSource) =>
                          onChangeModelSource(modelKey, nextSource)
                        }
                        options={sourceOptions}
                        className="shrink-0"
                      />
                    )}
                  </div>
                  <div className="truncate text-xs text-muted-foreground md:hidden">
                    {sourceLabel}
                  </div>
                </div>
                <ProtocolMultiSelect
                  value={protocols}
                  onChange={(next) => onChangeModelProtocols(modelKey, next)}
                  locale={locale}
                  disabled={isTargetOnly}
                  invalid={protocols.length === 0}
                  shouldRequireAtLeastOne
                />
                <span className="hidden truncate text-xs text-muted-foreground md:block">
                  {sourceLabel}
                </span>
                <div className="flex items-center justify-end gap-1">
                  {!isTargetOnly ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-8 px-2 text-muted-foreground hover:text-foreground"
                      onClick={() => testKey && onOpenModelTest(testKey)}
                      disabled={!testable || testingDisabled}
                    >
                      {locale === "zh-CN" ? "测试" : "Test"}
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                    aria-label={deleteLabel}
                    title={deleteLabel}
                    onClick={() => onRemoveModel(modelKey)}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </div>
              {isMultiKey && isExpanded ? (
                <div className="mb-1 ml-6 mt-1 flex flex-col divide-y">
                  {members.map((member) => {
                    const memberTestable = canTestModel(member.key);
                    const memberDeleteLabel = member.isTargetOnly
                      ? deleteTargetLabel
                      : deleteModelLabel;
                    return (
                      <div
                        key={member.key}
                        className="flex min-w-0 items-center gap-2 py-1"
                      >
                        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                          {member.credentialName}
                        </span>
                        {member.isTargetOnly ? (
                          <span className="shrink-0 text-xs text-amber-700 dark:text-amber-300">
                            {pendingLabel}
                          </span>
                        ) : (
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {member.source === "synced"
                              ? locale === "zh-CN"
                                ? "同步"
                                : "Synced"
                              : locale === "zh-CN"
                                ? "手动"
                                : "Manual"}
                          </span>
                        )}
                        {!member.isTargetOnly ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                            onClick={() => onOpenModelTest(member.key)}
                            disabled={!memberTestable || testingDisabled}
                          >
                            {locale === "zh-CN" ? "测试" : "Test"}
                          </Button>
                        ) : null}
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-muted-foreground hover:text-destructive"
                          aria-label={memberDeleteLabel}
                          title={memberDeleteLabel}
                          onClick={() => onRemoveModel(member.key)}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        },
      )}
    </div>
  );
}
