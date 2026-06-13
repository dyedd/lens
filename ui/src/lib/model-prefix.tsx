"use client";

import { LayoutGrid } from "lucide-react";
import {
  getModelFamilyKey,
  getModelFamilyLabel,
  ModelAvatar,
} from "@/lib/model-icons";
import { titleForLocale, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type ModelPrefixOption = {
  key: string;
  label: string;
  sampleModel: string;
};
export type SelectedModelPrefix = "all" | string;

export function buildModelPrefixOptions(
  names: string[],
  locale: Locale,
): ModelPrefixOption[] {
  const optionsByPrefix = new Map<string, ModelPrefixOption>();
  for (const name of names) {
    const prefix = getModelFamilyKey(name);
    if (prefix && !optionsByPrefix.has(prefix)) {
      optionsByPrefix.set(prefix, {
        key: prefix,
        label: getModelFamilyLabel(name),
        sampleModel: name,
      });
    }
  }
  const sorted = Array.from(optionsByPrefix.values()).sort((a, b) =>
    a.label.localeCompare(b.label, locale),
  );
  if (!sorted.length) return [];
  return [
    {
      key: "all" as const,
      label: titleForLocale(locale, "全部", "All"),
      sampleModel: "all",
    },
    ...sorted,
  ];
}

export function resolveEffectiveModelPrefix(
  options: ModelPrefixOption[],
  selected: SelectedModelPrefix,
): SelectedModelPrefix {
  return options.some((item) => item.key === selected) ? selected : "all";
}

export function SeriesChip({
  selected,
  label,
  sampleModel,
  onClick,
  isAll = false,
}: {
  selected: boolean;
  label: string;
  sampleModel: string;
  onClick: () => void;
  isAll?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        "group flex min-w-[76px] snap-start items-center justify-center rounded-[22px] border bg-card px-4 py-4 text-center transition-all",
        selected
          ? "border-primary bg-primary/[0.05] shadow-[0_0_0_1px_rgba(37,99,235,0.08)]"
          : "border-border/70 hover:border-primary/25 hover:bg-muted/20",
      )}
    >
      <span
        className={cn(
          "flex size-11 items-center justify-center rounded-2xl border bg-background",
          selected ? "border-primary/20 bg-primary/[0.06]" : "border-border/60",
        )}
      >
        {isAll ? (
          <LayoutGrid
            size={20}
            className={selected ? "text-primary" : "text-muted-foreground"}
          />
        ) : (
          <ModelAvatar name={sampleModel} size={28} />
        )}
      </span>
    </button>
  );
}
