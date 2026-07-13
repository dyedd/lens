import { SeriesChip } from "@/components/SeriesChip";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import type { RequestLogItem } from "@/lib/api";
import type { ModelPrefixOption, SelectedModelPrefix } from "@/lib/modelPrefix";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { RequestCard } from "./RequestCard";

type RequestLogResultsProps = {
  activeFilterCount: number;
  canOpenDetail: boolean;
  effectiveModelPrefix: SelectedModelPrefix;
  isError: boolean;
  isLoading: boolean;
  items: RequestLogItem[];
  locale: Locale;
  modelPrefixOptions: ModelPrefixOption[];
  showModelPrefixFilter: boolean;
  timeZone: string;
  onModelPrefixChange: (value: SelectedModelPrefix) => void;
  onOpenAttempts: (id: number) => void;
  onOpenDetail: (id: number) => void;
};

/** Render request log cards and pagination. */
export function RequestLogResults(props: RequestLogResultsProps) {
  const {
    activeFilterCount,
    canOpenDetail,
    effectiveModelPrefix,
    isError,
    isLoading,
    items,
    locale,
    modelPrefixOptions,
    showModelPrefixFilter,
    timeZone,
    onModelPrefixChange,
    onOpenAttempts,
    onOpenDetail,
  } = props;
  return (
    <div className="order-2 grid gap-4 xl:order-1">
      {showModelPrefixFilter ? (
        <div className="rounded-2xl border bg-card px-4 py-3 sm:px-5 sm:py-4">
          <div className="flex items-center justify-between gap-3 sm:mb-3">
            <div className="text-base font-semibold text-foreground">
              {titleForLocale(locale, "选择模型系列", "Choose model series")}
            </div>
          </div>
          <Combobox
            className="mt-3 w-full sm:hidden"
            value={effectiveModelPrefix}
            onChange={(event) => onModelPrefixChange(event.target.value)}
          >
            {modelPrefixOptions.map((option) => (
              <ComboboxOption key={option.key} value={option.key}>
                {option.label}
              </ComboboxOption>
            ))}
          </Combobox>
          <div className="hidden snap-x gap-3 overflow-x-auto pb-1 sm:flex">
            {modelPrefixOptions.map((option) => (
              <SeriesChip
                key={option.key}
                selected={effectiveModelPrefix === option.key}
                label={option.label}
                sampleModel={option.sampleModel}
                isAll={option.key === "all"}
                onClick={() => onModelPrefixChange(option.key)}
              />
            ))}
          </div>
        </div>
      ) : null}
      <div className="rounded-2xl border bg-card p-3 sm:p-4">
        {!isError && !isLoading && items.length === 0 ? (
          <div className="rounded-xl border border-dashed bg-background px-6 py-14 text-center text-sm text-muted-foreground">
            {activeFilterCount
              ? titleForLocale(
                  locale,
                  "当前筛选条件下没有请求日志。",
                  "No request logs match the current filters.",
                )
              : titleForLocale(
                  locale,
                  "暂无请求日志。",
                  "No request logs yet.",
                )}
          </div>
        ) : null}
        {items.length ? (
          <div className="flex flex-col gap-3">
            {items.map((item) => (
              <RequestCard
                key={item.id}
                item={item}
                locale={locale}
                timeZone={timeZone}
                canOpenDetail={canOpenDetail}
                onOpenDetail={() => onOpenDetail(item.id)}
                onOpenAttempts={() => onOpenAttempts(item.id)}
              />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
