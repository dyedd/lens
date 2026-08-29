import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import type { HeaderItem } from "./gatewaySettingsTypes";

type HeaderRowsProps = {
  title: string;
  headers: HeaderItem[];
  locale: Locale;
  onAdd: () => void;
  onUpdate: (index: number, patch: Partial<HeaderItem>) => void;
  onRemove: (index: number) => void;
};

/** Renders editable upstream request-header rows. */
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
      {headers.map((header, headerIndex) => (
        <div
          key={headerIndex}
          className="grid gap-3 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
        >
          <Field>
            <FieldLabel>
              {titleForLocale(locale, "请求头名称", "Header key")}
            </FieldLabel>
            <Input
              value={header.key}
              onChange={(event) =>
                onUpdate(headerIndex, { key: event.target.value })
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
              onChange={(event) =>
                onUpdate(headerIndex, { value: event.target.value })
              }
              placeholder="value"
            />
          </Field>
          <Field>
            <FieldLabel>{titleForLocale(locale, "动作", "Action")}</FieldLabel>
            <Select
              value={header.action}
              onValueChange={(value) =>
                onUpdate(headerIndex, {
                  action: value as HeaderItem["action"],
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="override">
                  {titleForLocale(locale, "覆盖", "Override")}
                </SelectItem>
                <SelectItem value="append">
                  {titleForLocale(locale, "追加", "Append")}
                </SelectItem>
                <SelectItem value="remove">
                  {titleForLocale(locale, "删除", "Remove")}
                </SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="text-muted-foreground"
            aria-label={titleForLocale(locale, "删除请求头", "Remove header")}
            onClick={() => onRemove(headerIndex)}
          >
            <Trash2 data-icon="inline-start" />
          </Button>
        </div>
      ))}
    </div>
  );
}
