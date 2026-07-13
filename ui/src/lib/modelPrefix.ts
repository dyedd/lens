import { getModelFamilyKey, getModelFamilyLabel } from "@/lib/ModelIcons";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

export type ModelPrefixOption = {
  key: string;
  label: string;
  sampleModel: string;
};
export type SelectedModelPrefix = "all" | string;

/** Builds localized model-family filter options from model names. */
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

/** Falls back to the all-model option when a selected prefix is unavailable. */
export function resolveEffectiveModelPrefix(
  options: ModelPrefixOption[],
  selected: SelectedModelPrefix,
): SelectedModelPrefix {
  return options.some((item) => item.key === selected) ? selected : "all";
}
