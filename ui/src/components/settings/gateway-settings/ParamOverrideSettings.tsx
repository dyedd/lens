import { Plus } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/Field";
import { Separator } from "@/components/ui/Separator";
import { Textarea } from "@/components/ui/Textarea";
import { titleForLocale } from "@/lib/I18nContext";

import type { ParamOverrideSettingsProps } from "./gatewaySettingsTypes";
import { ParamOverrideRuleCard } from "./ParamOverrideRuleCard";

/** Renders global and model-specific upstream parameter overrides. */
export function ParamOverrideSettings({
  locale,
  config,
  onGlobalChange,
  onAddRule,
  onUpdateRule,
  onRemoveRule,
  onMoveRule,
}: ParamOverrideSettingsProps) {
  return (
    <div className="flex flex-col gap-5 rounded-lg border bg-muted/20 p-4">
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
      <Separator />
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">
          {titleForLocale(
            locale,
            "模型参数覆盖规则",
            "Model param override rules",
          )}
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onAddRule}>
          <Plus data-icon="inline-start" />
          {titleForLocale(locale, "添加规则", "Add rule")}
        </Button>
      </div>
      {config.rules.length ? (
        <div className="flex flex-col gap-4">
          {config.rules.map((rule, ruleIndex) => (
            <ParamOverrideRuleCard
              key={rule.id}
              locale={locale}
              rule={rule}
              ruleIndex={ruleIndex}
              ruleCount={config.rules.length}
              onUpdate={(patch) => onUpdateRule(ruleIndex, patch)}
              onRemove={() => onRemoveRule(ruleIndex)}
              onMove={(direction) => onMoveRule(ruleIndex, direction)}
            />
          ))}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">
          {titleForLocale(locale, "暂无规则", "No rules")}
        </div>
      )}
      <FieldDescription>
        {titleForLocale(
          locale,
          "合并优先级：请求体 < 全局 < 规则 < 渠道覆盖（后者覆盖前者）。",
          "Merge priority: body < global < rules < channel override (later wins).",
        )}
      </FieldDescription>
    </div>
  );
}
