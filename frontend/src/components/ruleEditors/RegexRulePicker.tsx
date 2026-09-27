import { ChevronDown, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/Command";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { useRegexRules } from "@/hooks/useRegexRules";
import type { RegexRule } from "@/lib/api/regexRules";
import { type Locale, titleForLocale } from "@/lib/I18nContext";
import { formatRegexRuleUsage } from "@/lib/regexRules";
import {
  DeleteRegexRuleDialog,
  RegexRuleEditorDialog,
} from "./RegexRuleDialogs";

/** Most rules one sync filter or model group can reference. */
const MAX_RULE_REFS = 20;

/** Show an attached rule; its menu edits, detaches, or deletes the rule. */
function RegexRuleChip({
  rule,
  locale,
  onEdit,
  onDetach,
  onDelete,
}: {
  rule: RegexRule;
  locale: Locale;
  onEdit: () => void;
  onDetach: () => void;
  onDelete: () => void;
}) {
  return (
    <DropdownMenu modal={false}>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <button type="button" className="shrink-0 rounded-4xl">
              <Badge
                variant="outline"
                className="max-w-48 gap-0.5 pr-1 font-normal hover:bg-muted"
              >
                <span className="truncate">{rule.name}</span>
                <ChevronDown className="text-muted-foreground" />
              </Badge>
            </button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm flex-col items-start gap-0.5">
          <span className="font-medium">{rule.name}</span>
          <span className="break-all font-mono">{rule.pattern}</span>
          <span className="opacity-70">
            {formatRegexRuleUsage(rule, locale)}
          </span>
        </TooltipContent>
      </Tooltip>
      <DropdownMenuContent align="start">
        <DropdownMenuItem onSelect={onEdit}>
          <Pencil className="size-3.5 stroke-1" />
          {titleForLocale(locale, "编辑规则", "Edit rule")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onDetach}>
          <X className="size-3.5 stroke-1" />
          {titleForLocale(locale, "移出此处", "Remove from here")}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onDelete}>
          <Trash2 className="size-3.5 stroke-1" />
          {titleForLocale(locale, "从规则库删除", "Delete from library")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * Attach library rules to one field by id.
 *
 * Attaching and detaching change only `value`; editing or deleting a rule
 * writes to the library at once, so every field using it changes too.
 */
export function RegexRulePicker({
  value,
  onChange,
  locale,
  label,
  max = MAX_RULE_REFS,
}: {
  /** Attached rule ids. */
  value: string[];
  onChange: (ruleIds: string[]) => void;
  locale: Locale;
  /** Accessible name of the field. */
  label: string;
  max?: number;
}) {
  const library = useRegexRules();
  const [isAdding, setIsAdding] = useState(false);
  const [editor, setEditor] = useState<{ rule: RegexRule | null } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<RegexRule | null>(null);
  const rulesById = new Map(library.rules.map((rule) => [rule.id, rule]));
  const availableRules = library.rules.filter(
    (rule) => !value.includes(rule.id),
  );
  const isFull = value.length >= max;

  function attach(ruleId: string) {
    onChange([...value, ruleId]);
  }

  function detach(ruleId: string) {
    onChange(value.filter((id) => id !== ruleId));
  }

  const addButton = (
    <PopoverTrigger asChild>
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={!library.isLoaded || isFull}
        className="text-muted-foreground"
      >
        <Plus />
        {titleForLocale(locale, "添加", "Add")}
      </Button>
    </PopoverTrigger>
  );

  return (
    <fieldset
      aria-label={label}
      className="flex min-w-0 flex-wrap items-center gap-1 border-0 p-0"
    >
      {library.isLoaded ? (
        value.map((ruleId) => {
          const rule = rulesById.get(ruleId);
          return rule ? (
            <RegexRuleChip
              key={ruleId}
              rule={rule}
              locale={locale}
              onEdit={() => setEditor({ rule })}
              onDetach={() => detach(ruleId)}
              onDelete={() => setDeleteTarget(rule)}
            />
          ) : (
            <Badge key={ruleId} variant="secondary" className="gap-0.5 pr-0.5">
              {titleForLocale(locale, "已删除", "Deleted")}
              <button
                type="button"
                className="grid size-4 place-items-center rounded-full hover:bg-background hover:text-foreground"
                aria-label={titleForLocale(
                  locale,
                  "移除已删除的规则",
                  "Remove deleted rule",
                )}
                onClick={() => detach(ruleId)}
              >
                <X className="size-3" />
              </button>
            </Badge>
          );
        })
      ) : (
        <span
          className={
            library.isError
              ? "text-xs text-destructive"
              : "text-xs text-muted-foreground"
          }
        >
          {library.isError
            ? titleForLocale(locale, "规则库加载失败", "Failed to load rules")
            : titleForLocale(locale, "加载中...", "Loading...")}
        </span>
      )}
      <Popover open={isAdding} onOpenChange={setIsAdding}>
        {isFull ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex">{addButton}</span>
            </TooltipTrigger>
            <TooltipContent>
              {titleForLocale(
                locale,
                `最多 ${max} 条规则`,
                `At most ${max} rules`,
              )}
            </TooltipContent>
          </Tooltip>
        ) : (
          addButton
        )}
        <PopoverContent align="start" className="w-80 gap-0 p-0">
          <Command>
            <CommandInput
              className="h-9 text-xs"
              placeholder={titleForLocale(locale, "搜索规则", "Search rules")}
            />
            <CommandList className="max-h-60">
              <CommandEmpty className="py-4 text-xs">
                {!library.rules.length
                  ? titleForLocale(locale, "规则库为空", "The library is empty")
                  : !availableRules.length
                    ? titleForLocale(
                        locale,
                        "规则均已添加",
                        "Every rule is added",
                      )
                    : titleForLocale(locale, "无匹配规则", "No matching rules")}
              </CommandEmpty>
              {availableRules.map((rule) => (
                <CommandItem
                  key={rule.id}
                  value={`${rule.name} ${rule.pattern}`}
                  onSelect={() => {
                    attach(rule.id);
                    setIsAdding(false);
                  }}
                  className="flex-col items-start gap-0.5 text-xs"
                >
                  <span className="font-medium">{rule.name}</span>
                  <span className="break-all font-mono text-[11px] text-muted-foreground">
                    {rule.pattern}
                  </span>
                </CommandItem>
              ))}
            </CommandList>
          </Command>
          <div className="border-t border-border/60 p-1">
            <Button
              type="button"
              variant="ghost"
              size="xs"
              className="w-full justify-start text-muted-foreground"
              onClick={() => {
                setIsAdding(false);
                setEditor({ rule: null });
              }}
            >
              <Plus />
              {titleForLocale(locale, "新建规则", "New rule")}
            </Button>
          </div>
        </PopoverContent>
      </Popover>
      {editor ? (
        <RegexRuleEditorDialog
          locale={locale}
          rule={editor.rule}
          onClose={() => setEditor(null)}
          onSaved={editor.rule ? undefined : (rule) => attach(rule.id)}
        />
      ) : null}
      {deleteTarget ? (
        <DeleteRegexRuleDialog
          locale={locale}
          rule={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onDeleted={detach}
        />
      ) : null}
    </fieldset>
  );
}
