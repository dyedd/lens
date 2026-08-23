import { Field, FieldDescription, FieldLabel } from "@/components/ui/Field";
import { Textarea } from "@/components/ui/Textarea";
import { titleForLocale } from "@/lib/I18nContext";

import type { ParamOverrideSettingsProps } from "./gatewaySettingsTypes";

/** Renders the global upstream parameter override. */
export function ParamOverrideSettings({
  locale,
  config,
  onGlobalChange,
}: ParamOverrideSettingsProps) {
  return (
    <div className="rounded-lg border bg-muted/20 p-4">
      <Field>
        <FieldLabel>
          {titleForLocale(locale, "全局参数覆盖", "Global param override")}
        </FieldLabel>
        <Textarea
          className="min-h-[92px] font-mono text-sm"
          value={config.global}
          onChange={(event) => onGlobalChange(event.target.value)}
          placeholder={'{\n  "stream_options": { "include_usage": true }\n}'}
        />
        <FieldDescription>
          {titleForLocale(
            locale,
            "JSON 对象，深合并进所有协议的上游请求体；不可覆盖 model。",
            "JSON object, deep-merged into all protocols' upstream body; cannot override model.",
          )}
        </FieldDescription>
      </Field>
    </div>
  );
}
