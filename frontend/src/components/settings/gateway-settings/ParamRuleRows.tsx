import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import type { ParamOverrideRuleDraft } from "@/lib/upstreamRules";

type Props = {
  title: string;
  rules: ParamOverrideRuleDraft[];
  locale: Locale;
  onChange: (rules: ParamOverrideRuleDraft[]) => void;
};

const EMPTY_RULE: ParamOverrideRuleDraft = {
  path: "",
  action: "set",
  value: "",
};

/** Renders editable upstream parameter rules. */
export function ParamRuleRows({ title, rules, locale, onChange }: Props) {
  function updateRule(index: number, patch: Partial<ParamOverrideRuleDraft>) {
    onChange(
      rules.map((rule, currentIndex) =>
        currentIndex === index ? { ...rule, ...patch } : rule,
      ),
    );
  }

  function removeRule(index: number) {
    const nextRules = rules.filter((_, currentIndex) => currentIndex !== index);
    onChange(nextRules.length ? nextRules : [{ ...EMPTY_RULE }]);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onChange([...rules, { ...EMPTY_RULE }])}
        >
          <Plus data-icon="inline-start" />
          {titleForLocale(locale, "添加", "Add")}
        </Button>
      </div>
      {rules.length ? (
        <div className="max-h-72 overflow-y-auto pr-1">
          {rules.map((rule, index) => (
            <div
              key={index}
              className="grid gap-3 border-b py-3 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_140px_minmax(0,1fr)_auto]"
            >
              <Field>
                <FieldLabel>
                  {titleForLocale(locale, "路径", "Path")}
                </FieldLabel>
                <Input
                  value={rule.path}
                  onChange={(event) =>
                    updateRule(index, { path: event.target.value })
                  }
                  placeholder="metadata.trace"
                />
              </Field>
              <Field>
                <FieldLabel>
                  {titleForLocale(locale, "动作", "Action")}
                </FieldLabel>
                <select
                  className="h-9 rounded-md border bg-background px-2 text-sm"
                  value={rule.action}
                  onChange={(event) =>
                    updateRule(index, {
                      action: event.target
                        .value as ParamOverrideRuleDraft["action"],
                    })
                  }
                >
                  <option value="set">
                    {titleForLocale(locale, "设置", "Set")}
                  </option>
                  <option value="delete">
                    {titleForLocale(locale, "删除", "Delete")}
                  </option>
                </select>
              </Field>
              <Field>
                <FieldLabel>
                  {titleForLocale(locale, "JSON 值", "JSON value")}
                </FieldLabel>
                <Input
                  disabled={rule.action === "delete"}
                  value={rule.value}
                  onChange={(event) =>
                    updateRule(index, { value: event.target.value })
                  }
                  placeholder="true"
                />
              </Field>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="self-end text-muted-foreground"
                aria-label={titleForLocale(locale, "删除规则", "Remove rule")}
                onClick={() => removeRule(index)}
              >
                <Trash2 />
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
