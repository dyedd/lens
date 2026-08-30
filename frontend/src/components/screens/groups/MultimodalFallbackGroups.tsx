import { ChevronDown, ChevronsUpDown, ChevronUp, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/Command";
import { Field, FieldLabel } from "@/components/ui/Field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import type { ModelGroup } from "@/lib/api/groups";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

type Props = {
  locale: Locale;
  options: ModelGroup[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
};

/** Pick ordered multimodal fallback model groups for one source group. */
export function MultimodalFallbackGroups({
  locale,
  options,
  selectedIds,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const selectedGroups = selectedIds
    .map((id) => options.find((group) => group.id === id))
    .filter((group): group is ModelGroup => Boolean(group));
  const available = options.filter((group) => !selectedIds.includes(group.id));

  function move(from: number, to: number) {
    if (to < 0 || to >= selectedIds.length) return;
    const next = [...selectedIds];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    onChange(next);
  }

  return (
    <Field>
      <FieldLabel>
        {titleForLocale(
          locale,
          "多模态回退模型组",
          "Multimodal fallback groups",
        )}
      </FieldLabel>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            className="w-full justify-between font-normal"
          >
            <span className="truncate text-left">
              {selectedGroups.length
                ? selectedGroups.map((group) => group.name).join(" → ")
                : titleForLocale(
                    locale,
                    "选择回退模型组",
                    "Select fallback groups",
                  )}
            </span>
            <ChevronsUpDown className="text-muted-foreground" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-[var(--radix-popover-trigger-width)] p-0"
        >
          <Command>
            <CommandInput
              placeholder={titleForLocale(
                locale,
                "搜索模型组",
                "Search model groups",
              )}
            />
            <CommandList>
              <CommandEmpty>
                {titleForLocale(
                  locale,
                  "没有可用模型组",
                  "No model groups available",
                )}
              </CommandEmpty>
              {available.map((group) => (
                <CommandItem
                  key={group.id}
                  value={group.name}
                  onSelect={() => onChange([...selectedIds, group.id])}
                >
                  <span className="truncate">{group.name}</span>
                </CommandItem>
              ))}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {selectedGroups.length ? (
        <div className="mt-2 max-h-64 divide-y overflow-y-auto rounded-md bg-muted/20 px-2">
          {selectedGroups.map((group, index) => (
            <div
              key={group.id}
              className="flex items-center gap-2 py-2 text-sm"
            >
              <span className="min-w-0 flex-1 truncate">
                {index + 1}. {group.name}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                disabled={index === 0}
                aria-label={titleForLocale(locale, "上移", "Move up")}
                onClick={() => move(index, index - 1)}
              >
                <ChevronUp />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                disabled={index === selectedGroups.length - 1}
                aria-label={titleForLocale(locale, "下移", "Move down")}
                onClick={() => move(index, index + 1)}
              >
                <ChevronDown />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={titleForLocale(locale, "删除", "Remove")}
                onClick={() =>
                  onChange(selectedIds.filter((id) => id !== group.id))
                }
              >
                <Trash2 />
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </Field>
  );
}
