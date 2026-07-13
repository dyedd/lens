import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Switch } from "@/components/ui/Switch";
import { Textarea } from "@/components/ui/Textarea";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import type {
  HeaderItem,
  UpstreamHeaderMatchType,
  UpstreamHeaderRuleDraft,
} from "./gatewaySettingsTypes";
import { HeaderRows } from "./HeaderRows";

type UpstreamHeaderRuleCardProps = {
  locale: Locale;
  rule: UpstreamHeaderRuleDraft;
  ruleIndex: number;
  ruleCount: number;
  onUpdate: (patch: Partial<UpstreamHeaderRuleDraft>) => void;
  onRemove: () => void;
  onMove: (direction: -1 | 1) => void;
  onAddHeader: () => void;
  onUpdateHeader: (index: number, patch: Partial<HeaderItem>) => void;
  onRemoveHeader: (index: number) => void;
};

/** Renders one ordered model-specific upstream-header rule. */
export function UpstreamHeaderRuleCard({
  locale,
  rule,
  ruleIndex,
  ruleCount,
  onUpdate,
  onRemove,
  onMove,
  onAddHeader,
  onUpdateHeader,
  onRemoveHeader,
}: UpstreamHeaderRuleCardProps) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border bg-background p-3">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-end">
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "规则名称", "Rule name")}
          </FieldLabel>
          <Input
            value={rule.name}
            onChange={(event) => onUpdate({ name: event.target.value })}
            placeholder={titleForLocale(locale, "规则名称", "Rule name")}
          />
        </Field>
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "匹配方式", "Match type")}
          </FieldLabel>
          <SegmentedControl<UpstreamHeaderMatchType>
            value={rule.matchType}
            onValueChange={(matchType) => onUpdate({ matchType })}
            options={[
              {
                value: "exact",
                label: titleForLocale(locale, "精确", "Exact"),
              },
              {
                value: "regex",
                label: titleForLocale(locale, "正则", "Regex"),
              },
            ]}
          />
        </Field>
        <div className="flex items-center justify-between gap-2 lg:justify-end">
          <Switch
            checked={rule.enabled}
            aria-label={titleForLocale(locale, "启用规则", "Enable rule")}
            onCheckedChange={(enabled) => onUpdate({ enabled })}
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            aria-label={titleForLocale(locale, "上移规则", "Move rule up")}
            disabled={ruleIndex === 0}
            onClick={() => onMove(-1)}
          >
            <ArrowUp data-icon="inline-start" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            aria-label={titleForLocale(locale, "下移规则", "Move rule down")}
            disabled={ruleIndex === ruleCount - 1}
            onClick={() => onMove(1)}
          >
            <ArrowDown data-icon="inline-start" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="text-muted-foreground"
            aria-label={titleForLocale(locale, "删除规则", "Remove rule")}
            onClick={onRemove}
          >
            <Trash2 data-icon="inline-start" />
          </Button>
        </div>
      </div>
      {rule.matchType === "exact" ? (
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "模型名称", "Models")}
          </FieldLabel>
          <Textarea
            className="min-h-[84px]"
            value={rule.models}
            onChange={(event) => onUpdate({ models: event.target.value })}
            placeholder={"gpt-5.5\ngpt-5.4-mini"}
          />
        </Field>
      ) : (
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "模型正则", "Model regex")}
          </FieldLabel>
          <Input
            value={rule.pattern}
            onChange={(event) => onUpdate({ pattern: event.target.value })}
            placeholder="^claude-"
          />
        </Field>
      )}
      <HeaderRows
        title={titleForLocale(locale, "规则请求头", "Rule headers")}
        headers={rule.headers}
        locale={locale}
        onAdd={onAddHeader}
        onUpdate={onUpdateHeader}
        onRemove={onRemoveHeader}
      />
    </div>
  );
}
