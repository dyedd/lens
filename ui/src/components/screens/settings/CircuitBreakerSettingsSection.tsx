import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { TabsContent } from "@/components/ui/Tabs";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { SettingsSectionCard } from "./SettingsSectionCard";
import { type useSettingsDraft } from "./useSettingsDraft";

type CircuitBreakerKey =
  | "circuitBreakerThreshold"
  | "circuitBreakerCooldown"
  | "circuitBreakerMaxCooldown"
  | "healthWindowSeconds"
  | "healthPenaltyWeight"
  | "healthMinSamples";

type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

interface NumberSettingFieldProps {
  label: string;
  min: string;
  step?: string;
  value: string;
  onChange: (value: string) => void;
}

function NumberSettingField({
  label,
  min,
  step,
  value,
  onChange,
}: NumberSettingFieldProps) {
  return (
    <Field>
      <FieldLabel>{label}</FieldLabel>
      <Input
        type="number"
        min={min}
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  );
}

function _getCircuitBreakerFields(locale: Locale) {
  return [
    {
      key: "circuitBreakerThreshold",
      label: titleForLocale(locale, "失败阈值", "Failure threshold"),
      min: "0",
    },
    {
      key: "circuitBreakerCooldown",
      label: titleForLocale(locale, "基础冷却秒数", "Cooldown seconds"),
      min: "0",
    },
    {
      key: "circuitBreakerMaxCooldown",
      label: titleForLocale(locale, "最大冷却秒数", "Max cooldown seconds"),
      min: "0",
    },
    {
      key: "healthWindowSeconds",
      label: titleForLocale(locale, "健康窗口秒数", "Health window seconds"),
      min: "1",
    },
    {
      key: "healthPenaltyWeight",
      label: titleForLocale(locale, "健康惩罚权重", "Health penalty weight"),
      min: "0",
      step: "0.1",
    },
    {
      key: "healthMinSamples",
      label: titleForLocale(locale, "健康最小样本数", "Health min samples"),
      min: "1",
    },
  ] satisfies ReadonlyArray<{
    key: CircuitBreakerKey;
    label: string;
    min: string;
    step?: string;
  }>;
}

/** Render circuit breaker and health scoring settings. */
export function CircuitBreakerSettingsSection({
  description,
  locale,
  settings,
}: {
  description: string;
  locale: Locale;
  settings: SettingsDraftController;
}) {
  return (
    <TabsContent value="circuit-breaker" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(locale, "熔断器", "Circuit breaker")}
        description={description}
      >
        <FieldGroup>
          {_getCircuitBreakerFields(locale).map((field) => (
            <NumberSettingField
              key={field.key}
              label={field.label}
              min={field.min}
              step={field.step}
              value={settings.draft[field.key]}
              onChange={(value) => settings.setDraftValue(field.key, value)}
            />
          ))}
        </FieldGroup>
      </SettingsSectionCard>
    </TabsContent>
  );
}
