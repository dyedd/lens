import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import type { HeaderRuleDraft } from "@/lib/upstreamRules";

export type HeaderRowsProps = {
  title: string;
  headers: HeaderRuleDraft[];
  locale: Locale;
  onAdd: () => void;
  onUpdate: (index: number, patch: Partial<HeaderRuleDraft>) => void;
  onRemove: (index: number) => void;
};

/** Renders editable upstream request-header rules. */
export function HeaderRows({
  title,
  headers,
  locale,
  onAdd,
  onUpdate,
  onRemove,
}: HeaderRowsProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          <Plus data-icon="inline-start" />
          {titleForLocale(locale, "添加", "Add")}
        </Button>
      </div>
      {headers.length ? (
        <div className="max-h-72 overflow-y-auto pr-1">
          {headers.map((header, index) => (
            <div
              key={index}
              className="grid gap-3 border-b py-3 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
            >
              <Field>
                <FieldLabel>
                  {titleForLocale(locale, "请求头名称", "Header key")}
                </FieldLabel>
                <Input
                  value={header.key}
                  onChange={(event) =>
                    onUpdate(index, { key: event.target.value })
                  }
                  placeholder="X-Header-Name"
                />
              </Field>
              <Field>
                <FieldLabel>
                  {titleForLocale(locale, "请求头值", "Header value")}
                </FieldLabel>
                <Input
                  value={header.value}
                  disabled={header.action === "remove"}
                  onChange={(event) =>
                    onUpdate(index, { value: event.target.value })
                  }
                  placeholder="value"
                />
              </Field>
              <div className="flex items-end gap-2">
                <select
                  aria-label={titleForLocale(
                    locale,
                    "请求头动作",
                    "Header action",
                  )}
                  className="h-9 min-w-28 rounded-md border bg-background px-2 text-sm"
                  value={header.action}
                  onChange={(event) =>
                    onUpdate(index, {
                      action: event.target.value as HeaderRuleDraft["action"],
                    })
                  }
                >
                  <option value="override">
                    {titleForLocale(locale, "覆盖", "Override")}
                  </option>
                  <option value="append">
                    {titleForLocale(locale, "追加", "Append")}
                  </option>
                  <option value="remove">
                    {titleForLocale(locale, "删除", "Remove")}
                  </option>
                </select>
                <Button
                  type="button"
                  variant="destructive"
                  size="icon"
                  aria-label={titleForLocale(
                    locale,
                    "删除请求头",
                    "Remove header",
                  )}
                  title={titleForLocale(locale, "删除请求头", "Remove header")}
                  onClick={() => onRemove(index)}
                >
                  <Trash2 />
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
