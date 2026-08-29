import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import type { UpstreamParamOverrideDraft } from "@/lib/settingsTypes";

import type { ParamOverrideSettingsProps } from "./gatewaySettingsTypes";

export function ParamOverrideSettings({
  locale,
  config,
  onGlobalChange,
}: ParamOverrideSettingsProps) {
  return (
    <div className="rounded-lg border bg-muted/20 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-medium">
          {titleForLocale(locale, "全局参数规则", "Global parameter rules")}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            onGlobalChange([
              ...config.rules,
              { path: "", action: "set", value: "" },
            ])
          }
        >
          <Plus data-icon="inline-start" />
          {titleForLocale(locale, "添加", "Add")}
        </Button>
      </div>
      <div className="grid gap-3">
        {config.rules.map((rule, index) => (
          <div
            key={`${rule.path}-${index}`}
            className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_140px_minmax(0,1fr)_auto]"
          >
            <Field>
              <FieldLabel>{titleForLocale(locale, "路径", "Path")}</FieldLabel>
              <Input
                value={rule.path}
                onChange={(event) =>
                  onGlobalChange(
                    updateRule(config, index, { path: event.target.value }),
                  )
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
                  onGlobalChange(
                    updateRule(config, index, {
                      action: event.target.value as "set" | "delete",
                    }),
                  )
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
                  onGlobalChange(
                    updateRule(config, index, { value: event.target.value }),
                  )
                }
                placeholder="true"
              />
            </Field>
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label={titleForLocale(locale, "删除规则", "Remove rule")}
              onClick={() =>
                onGlobalChange(
                  config.rules.filter(
                    (_, currentIndex) => currentIndex !== index,
                  ),
                )
              }
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

function updateRule(
  config: UpstreamParamOverrideDraft,
  index: number,
  patch: Partial<UpstreamParamOverrideDraft["rules"][number]>,
) {
  return config.rules.map((rule, currentIndex) =>
    currentIndex === index ? { ...rule, ...patch } : rule,
  );
}
