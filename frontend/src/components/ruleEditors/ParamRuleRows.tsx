import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
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
    <div className="space-y-2">
      <div className="flex h-9 items-center justify-between gap-3">
        <h4 className="text-xs font-medium text-foreground/88">{title}</h4>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 gap-1.5 px-2 text-xs text-muted-foreground shadow-none"
          onClick={() => onChange([...rules, { ...EMPTY_RULE }])}
        >
          <Plus className="size-3.5" />
          {titleForLocale(locale, "添加", "Add")}
        </Button>
      </div>
      {rules.length ? (
        <div className="space-y-2">
          {rules.map((rule, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                className="min-w-0 flex-1"
                value={rule.path}
                onChange={(event) =>
                  updateRule(index, { path: event.target.value })
                }
                placeholder="metadata.trace"
                aria-label={titleForLocale(locale, "路径", "Path")}
              />
              <Select
                value={rule.action}
                onValueChange={(value) =>
                  updateRule(index, {
                    action: value as ParamOverrideRuleDraft["action"],
                  })
                }
              >
                <SelectTrigger
                  className="h-8 w-[5.5rem] shrink-0"
                  aria-label={titleForLocale(locale, "动作", "Action")}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="set">
                    {titleForLocale(locale, "设置", "Set")}
                  </SelectItem>
                  <SelectItem value="delete">
                    {titleForLocale(locale, "删除", "Delete")}
                  </SelectItem>
                </SelectContent>
              </Select>
              <Input
                className="min-w-0 flex-1"
                disabled={rule.action === "delete"}
                value={rule.value}
                onChange={(event) =>
                  updateRule(index, { value: event.target.value })
                }
                placeholder="true"
                aria-label={titleForLocale(locale, "JSON 值", "JSON value")}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="shrink-0 text-muted-foreground shadow-none"
                aria-label={titleForLocale(locale, "删除规则", "Remove rule")}
                onClick={() => removeRule(index)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
