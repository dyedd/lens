"use client";

import type { KeyboardEvent } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/Command";
import { Input } from "@/components/ui/Input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { cn } from "@/lib/utils";
import type { ModelGroup, ModelGroupEnsureResultItem } from "@/lib/api";
import type { Locale } from "./channelShared";

type Props = {
  item: ModelGroupEnsureResultItem;
  targetModelGroups: ModelGroup[];
  targetGroupIsSelectable: boolean;
  createGroupName: string;
  createGroupNameError?: string;
  isConfirming: boolean;
  isOpen: boolean;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onSelectCreate: () => void;
  onSelectExisting: (groupName: string) => void;
  onDraftChange: (value: string) => void;
  onCommitDraft: () => void;
};

/** Selects an existing target group or configures a new group name. */
export function ModelGroupTargetSelector({
  item,
  targetModelGroups,
  targetGroupIsSelectable,
  createGroupName,
  createGroupNameError,
  isConfirming,
  isOpen,
  locale,
  onOpenChange,
  onSelectCreate,
  onSelectExisting,
  onDraftChange,
  onCommitDraft,
}: Props) {
  const createValue = "__create__";
  const targetValue = targetGroupIsSelectable ? item.group_name : createValue;

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    onCommitDraft();
  }

  return (
    <div className="flex max-w-[360px] flex-col gap-1.5">
      <Popover open={isOpen} onOpenChange={onOpenChange}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={isConfirming}
            role="combobox"
            aria-expanded={isOpen}
            className="w-full justify-between"
          >
            <span className="truncate">
              {targetValue === createValue
                ? locale === "zh-CN"
                  ? "新建模型组"
                  : "Create group"
                : item.group_name}
            </span>
            <ChevronsUpDown data-icon="inline-end" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-[var(--radix-popover-trigger-width)] p-0"
        >
          <Command>
            <CommandInput
              placeholder={
                locale === "zh-CN" ? "搜索模型组..." : "Search groups..."
              }
            />
            <CommandList>
              <CommandEmpty>
                {locale === "zh-CN" ? "没有匹配的模型组" : "No matching groups"}
              </CommandEmpty>
              <CommandGroup heading={locale === "zh-CN" ? "操作" : "Action"}>
                <CommandItem
                  value={`${createValue} ${createGroupName} ${item.model_name}`}
                  forceMount
                  onSelect={onSelectCreate}
                >
                  <div className="flex min-w-0 flex-col">
                    <span>
                      {locale === "zh-CN" ? "新建模型组" : "Create group"}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {createGroupName}
                    </span>
                  </div>
                  <Check
                    className={cn(
                      "ml-auto",
                      targetValue === createValue ? "opacity-100" : "opacity-0",
                    )}
                  />
                </CommandItem>
              </CommandGroup>
              {targetModelGroups.length ? (
                <>
                  <CommandSeparator />
                  <CommandGroup
                    heading={
                      locale === "zh-CN" ? "已有模型组" : "Existing groups"
                    }
                  >
                    {targetModelGroups.map((group) => (
                      <CommandItem
                        key={group.id}
                        value={group.name}
                        onSelect={() => onSelectExisting(group.name)}
                      >
                        <span className="truncate">{group.name}</span>
                        <Check
                          className={cn(
                            "ml-auto",
                            item.group_name === group.name
                              ? "opacity-100"
                              : "opacity-0",
                          )}
                        />
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </>
              ) : null}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {targetValue === createValue ? (
        <Input
          value={createGroupName}
          disabled={isConfirming}
          placeholder={locale === "zh-CN" ? "模型组名称" : "Group name"}
          aria-label={locale === "zh-CN" ? "新建模型组名称" : "New group name"}
          onChange={(event) => onDraftChange(event.target.value)}
          onBlur={onCommitDraft}
          onKeyDown={handleKeyDown}
        />
      ) : null}
      {targetValue === createValue && createGroupNameError ? (
        <p className="text-xs text-destructive">{createGroupNameError}</p>
      ) : null}
    </div>
  );
}
