import type { Dispatch, SetStateAction } from "react";
import { SeriesChip } from "@/components/SeriesChip";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import type { ModelPrefixOption, SelectedModelPrefix } from "@/lib/modelPrefix";

interface ModelSeriesSelectorProps {
  locale: "zh-CN" | "en-US";
  modelPrefixOptions: ModelPrefixOption[];
  selectedModelPrefix: SelectedModelPrefix;
  setSelectedModelPrefix: Dispatch<SetStateAction<SelectedModelPrefix>>;
}

/** Render mobile and desktop model-series selectors. */
export function ModelSeriesSelector({
  locale,
  modelPrefixOptions,
  selectedModelPrefix,
  setSelectedModelPrefix,
}: ModelSeriesSelectorProps) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-3 sm:px-5 sm:py-4">
      <div className="flex items-center justify-between gap-3 sm:mb-3">
        <div className="text-base font-semibold text-foreground">
          {locale === "zh-CN" ? "选择模型系列" : "Choose model series"}
        </div>
      </div>

      <Combobox
        className="mt-3 w-full sm:hidden"
        value={selectedModelPrefix}
        onChange={(event) => setSelectedModelPrefix(event.target.value)}
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
            selected={selectedModelPrefix === option.key}
            label={option.label}
            sampleModel={option.sampleModel}
            isAll={option.key === "all"}
            onClick={() => setSelectedModelPrefix(option.key)}
          />
        ))}
      </div>
    </div>
  );
}
