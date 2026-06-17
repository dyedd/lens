"use client";

import * as React from "react";
import { CheckIcon, ChevronsUpDownIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

type ComboboxProps = Omit<React.ComponentProps<"select">, "size"> & {
  size?: "sm" | "default";
};

type OptionItem = {
  disabled: boolean;
  label: string;
  searchValue: string;
  value: string;
};

type OptionGroup = {
  label?: string;
  options: OptionItem[];
};

function Combobox({
  className,
  size = "default",
  children,
  defaultValue,
  disabled,
  id,
  onChange,
  value,
  "aria-invalid": ariaInvalid,
  "aria-label": ariaLabel,
  autoFocus,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [internalValue, setInternalValue] = React.useState(() =>
    stringifySelectValue(defaultValue),
  );
  const listId = React.useId();
  const optionGroups = React.useMemo(
    () => extractOptionGroups(children),
    [children],
  );
  const options = React.useMemo(
    () => optionGroups.flatMap((group) => group.options),
    [optionGroups],
  );
  const currentValue =
    value === undefined ? internalValue : stringifySelectValue(value);
  const selectedOption = options.find(
    (option) => option.value === currentValue,
  );
  const selectedLabel =
    selectedOption?.label || (currentValue ? currentValue : "Select");

  function selectValue(nextValue: string) {
    const nextOption = options.find((option) => option.value === nextValue);

    if (!nextOption || nextOption.disabled) {
      return;
    }

    setOpen(false);

    if (nextValue === currentValue) {
      return;
    }

    if (value === undefined) {
      setInternalValue(nextValue);
    }

    onChange?.(createSelectChangeEvent(nextValue));
  }

  return (
    <div
      className={cn(
        "group/combobox relative w-fit has-[button:disabled]:opacity-50",
        className,
      )}
      data-slot="combobox-wrapper"
      data-size={size}
    >
      <Popover
        open={open}
        onOpenChange={(nextOpen) => {
          if (!disabled) setOpen(nextOpen);
        }}
      >
        <PopoverTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            size={size === "sm" ? "sm" : "default"}
            role="combobox"
            aria-controls={listId}
            aria-expanded={open}
            aria-invalid={ariaInvalid}
            aria-label={ariaLabel}
            autoFocus={autoFocus}
            disabled={disabled}
            className={cn(
              "w-full min-w-0 justify-between font-normal",
              !selectedOption && !currentValue && "text-muted-foreground",
            )}
          >
            <span className="truncate text-left">{selectedLabel}</span>
            <ChevronsUpDownIcon
              data-icon="inline-end"
              className="text-muted-foreground"
            />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-[var(--radix-popover-trigger-width)] p-0"
        >
          <Command>
            <CommandInput aria-label="Search options" />
            <CommandList id={listId}>
              <CommandEmpty>No matching options</CommandEmpty>
              {optionGroups.map((group, groupIndex) => (
                <CommandGroup key={groupIndex} heading={group.label}>
                  {group.options.map((option) => (
                    <CommandItem
                      key={`${groupIndex}:${option.value}:${option.label}`}
                      value={option.searchValue}
                      disabled={option.disabled}
                      onSelect={() => selectValue(option.value)}
                    >
                      <span className="truncate">{option.label}</span>
                      <CheckIcon
                        className={cn(
                          "ml-auto",
                          currentValue === option.value
                            ? "opacity-100"
                            : "opacity-0",
                        )}
                      />
                    </CommandItem>
                  ))}
                </CommandGroup>
              ))}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}

function ComboboxOption({
  className,
  ...props
}: React.ComponentProps<"option">) {
  return (
    <option
      data-slot="combobox-option"
      className={cn("bg-[Canvas] text-[CanvasText]", className)}
      {...props}
    />
  );
}

function ComboboxOptGroup({
  className,
  ...props
}: React.ComponentProps<"optgroup">) {
  return (
    <optgroup
      data-slot="combobox-optgroup"
      className={cn("bg-[Canvas] text-[CanvasText]", className)}
      {...props}
    />
  );
}

function stringifySelectValue(
  value: ComboboxProps["value"] | ComboboxProps["defaultValue"],
) {
  return value === undefined || value === null ? "" : String(value);
}

function createSelectChangeEvent(
  value: string,
): React.ChangeEvent<HTMLSelectElement> {
  const target = { name: "", value };

  return {
    currentTarget: target,
    target,
  } as unknown as React.ChangeEvent<HTMLSelectElement>;
}

function extractOptionGroups(children: React.ReactNode): OptionGroup[] {
  const groups: OptionGroup[] = [];
  const looseOptions: OptionItem[] = [];

  React.Children.forEach(children, (child) => {
    if (isOptionElement(child)) {
      looseOptions.push(optionFromElement(child));
      return;
    }

    if (isOptGroupElement(child)) {
      const options: OptionItem[] = [];

      React.Children.forEach(child.props.children, (groupChild) => {
        if (isOptionElement(groupChild)) {
          options.push(optionFromElement(groupChild, child.props.label));
        }
      });

      groups.push({
        label: typeof child.props.label === "string" ? child.props.label : "",
        options,
      });
    }
  });

  if (looseOptions.length > 0) {
    groups.unshift({ options: looseOptions });
  }

  return groups;
}

function isOptionElement(
  child: React.ReactNode,
): child is React.ReactElement<React.ComponentProps<"option">> {
  return (
    React.isValidElement<React.ComponentProps<"option">>(child) &&
    (child.type === "option" || child.type === ComboboxOption)
  );
}

function isOptGroupElement(
  child: React.ReactNode,
): child is React.ReactElement<React.ComponentProps<"optgroup">> {
  return (
    React.isValidElement<React.ComponentProps<"optgroup">>(child) &&
    (child.type === "optgroup" || child.type === ComboboxOptGroup)
  );
}

function optionFromElement(
  option: React.ReactElement<React.ComponentProps<"option">>,
  groupLabel?: React.ReactNode,
): OptionItem {
  const label = textFromNode(option.props.children);
  const value =
    option.props.value === undefined ? label : String(option.props.value);
  const groupText = textFromNode(groupLabel);

  return {
    disabled: Boolean(option.props.disabled),
    label,
    searchValue: [label, value, groupText].filter(Boolean).join(" "),
    value,
  };
}

function textFromNode(node: React.ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (Array.isArray(node)) {
    return node.map(textFromNode).join("");
  }

  if (React.isValidElement<{ children?: React.ReactNode }>(node)) {
    return textFromNode(node.props.children);
  }

  return "";
}

export { Combobox, ComboboxOptGroup, ComboboxOption };
