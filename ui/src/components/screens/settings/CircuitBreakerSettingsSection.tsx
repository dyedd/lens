import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
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
  id: string;
  label: string;
  min: string;
  max?: string;
  step?: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}

function NumberSettingField({
  id,
  label,
  min,
  max,
  step,
  value,
  error,
  onChange,
}: NumberSettingFieldProps) {
  return (
    <Field data-invalid={Boolean(error)}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        type="number"
        required
        min={min}
        max={max}
        step={step}
        value={value}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? <FieldError id={`${id}-error`}>{error}</FieldError> : null}
    </Field>
  );
}

function _getCircuitBreakerFields(locale: Locale) {
  return [
    {
      key: "circuitBreakerThreshold",
      id: "settings-circuit-breaker-threshold",
      label: titleForLocale(locale, "失败阈值", "Failure threshold"),
      min: "1",
    },
    {
      key: "circuitBreakerCooldown",
      id: "settings-circuit-breaker-cooldown",
      label: titleForLocale(locale, "基础冷却秒数", "Cooldown seconds"),
      min: "0",
      max: "604800",
    },
    {
      key: "circuitBreakerMaxCooldown",
      id: "settings-circuit-breaker-max-cooldown",
      label: titleForLocale(locale, "最大冷却秒数", "Max cooldown seconds"),
      min: "0",
      max: "604800",
    },
    {
      key: "healthWindowSeconds",
      id: "settings-health-window-seconds",
      label: titleForLocale(locale, "健康窗口秒数", "Health window seconds"),
      min: "1",
    },
    {
      key: "healthPenaltyWeight",
      id: "settings-health-penalty-weight",
      label: titleForLocale(locale, "健康惩罚权重", "Health penalty weight"),
      min: "0",
      step: "any",
    },
    {
      key: "healthMinSamples",
      id: "settings-health-min-samples",
      label: titleForLocale(locale, "健康最小样本数", "Health min samples"),
      min: "1",
    },
  ] satisfies ReadonlyArray<{
    key: CircuitBreakerKey;
    id: string;
    label: string;
    min: string;
    max?: string;
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
              id={field.id}
              label={field.label}
              min={field.min}
              max={field.max}
              step={field.step}
              value={settings.draft[field.key]}
              error={settings.numericSettingErrors[field.key]}
              onChange={(value) => settings.setDraftValue(field.key, value)}
            />
          ))}
        </FieldGroup>
      </SettingsSectionCard>
    </TabsContent>
  );
}
