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
    <div className="space-y-2">
      <div className="flex h-9 items-center justify-between gap-3">
        <h4 className="text-xs font-medium text-foreground/88">{title}</h4>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 gap-1.5 px-2 text-xs text-muted-foreground shadow-none"
          onClick={onAdd}
        >
          <Plus className="size-3.5" />
          {titleForLocale(locale, "添加", "Add")}
        </Button>
      </div>
      {headers.length ? (
        <div className="space-y-2">
          {headers.map((header, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                className="min-w-0 flex-1"
                value={header.key}
                onChange={(event) =>
                  onUpdate(index, { key: event.target.value })
                }
                placeholder="X-Header-Name"
                aria-label={titleForLocale(locale, "请求头名称", "Header key")}
              />
              <Input
                className="min-w-0 flex-1"
                value={header.value}
                disabled={header.action === "remove"}
                onChange={(event) =>
                  onUpdate(index, { value: event.target.value })
                }
                placeholder="value"
                aria-label={titleForLocale(locale, "请求头值", "Header value")}
              />
              <Select
                value={header.action}
                onValueChange={(value) =>
                  onUpdate(index, {
                    action: value as HeaderRuleDraft["action"],
                  })
                }
              >
                <SelectTrigger
                  className="h-8 w-[5.5rem] shrink-0"
                  aria-label={titleForLocale(
                    locale,
                    "请求头动作",
                    "Header action",
                  )}
                >
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
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="shrink-0 text-muted-foreground shadow-none"
                aria-label={titleForLocale(
                  locale,
                  "删除请求头",
                  "Remove header",
                )}
                onClick={() => onRemove(index)}
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
