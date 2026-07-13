"use client";

import { useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input } from "@/components/ui/Input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { cn } from "@/lib/utils";
import type { Locale } from "./channelShared";

export type CredentialOption = {
  id: string;
  display_name: string;
  enabled: boolean;
  api_key: string;
};

type Props = {
  value: string[];
  options: CredentialOption[];
  locale: Locale;
  invalid: boolean;
  onChange: (next: string[]) => void;
};

/** Renders a searchable multi-select for channel credentials. */
export function CredentialMultiSelect({
  value,
  options,
  locale,
  invalid,
  onChange,
}: Props) {
  const [searchQuery, setSearchQuery] = useState("");
  const optionById = new Map(options.map((item) => [item.id, item]));
  const selectedInOrder = [
    ...options.filter((item) => value.includes(item.id)).map((item) => item.id),
    ...value.filter((id) => !optionById.has(id)),
  ];
  const selectedOptions = selectedInOrder.map((id) => ({
    id,
    label:
      optionById.get(id)?.display_name ||
      (locale === "zh-CN" ? "未知密钥" : "Unknown key"),
    available:
      Boolean(optionById.get(id)?.enabled) &&
      Boolean(optionById.get(id)?.api_key.trim()),
  }));
  const normalizedSearchQuery = searchQuery.trim().toLowerCase();
  const filteredOptions = normalizedSearchQuery
    ? options.filter((item) =>
        [item.display_name, item.id].some((text) =>
          text.toLowerCase().includes(normalizedSearchQuery),
        ),
      )
    : options;
  const isMultiColumn = filteredOptions.length > 4;

  const toggle = (id: string) => {
    onChange(
      value.includes(id) ? value.filter((item) => item !== id) : [...value, id],
    );
  };

  return (
    <Popover
      onOpenChange={(open) => {
        if (!open) setSearchQuery("");
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          aria-invalid={invalid || undefined}
          className={cn(
            "w-full justify-between px-3 font-normal",
            selectedOptions.length === 0 && "text-muted-foreground",
          )}
        >
          {selectedOptions.length ? (
            <span className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden">
              {selectedOptions.slice(0, 2).map((item) => (
                <span
                  key={item.id}
                  className={cn(
                    "truncate text-xs",
                    item.available
                      ? "text-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  {item.label}
                </span>
              ))}
              {selectedOptions.length > 2 ? (
                <span className="shrink-0 text-xs text-muted-foreground">
                  +{selectedOptions.length - 2}
                </span>
              ) : null}
            </span>
          ) : (
            <span className="truncate">
              {locale === "zh-CN" ? "选择密钥" : "Select keys"}
            </span>
          )}
          <ChevronDown />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className={cn(
          "p-2",
          isMultiColumn
            ? "w-80"
            : "w-max min-w-[var(--radix-popover-trigger-width)]",
        )}
      >
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="h-8 pl-8"
            placeholder={locale === "zh-CN" ? "搜索密钥" : "Search keys"}
          />
        </div>
        {filteredOptions.length ? (
          <div className={cn("grid gap-1", isMultiColumn && "grid-cols-2")}>
            {filteredOptions.map((item) => {
              const checked = value.includes(item.id);
              const isAvailable = item.enabled && item.api_key.trim();
              const checkboxId = `credential-opt-${item.id}`;
              return (
                <div
                  key={item.id}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted"
                >
                  <Checkbox
                    id={checkboxId}
                    checked={checked}
                    onCheckedChange={() => toggle(item.id)}
                  />
                  <label
                    htmlFor={checkboxId}
                    className="min-w-0 flex-1 cursor-pointer truncate"
                  >
                    {item.display_name}
                  </label>
                  {!isAvailable ? (
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {locale === "zh-CN" ? "不可用" : "Unavailable"}
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="px-2 py-1.5 text-sm text-muted-foreground">
            {locale === "zh-CN" ? "没有匹配密钥" : "No matching keys"}
          </div>
        )}
        {selectedOptions.length ? (
          <div className="mt-2 flex items-center justify-between border-t pt-2 text-xs text-muted-foreground">
            <span>
              {locale === "zh-CN"
                ? `已选 ${selectedOptions.length} 个`
                : `${selectedOptions.length} selected`}
            </span>
            <button
              type="button"
              className="text-foreground hover:underline"
              onClick={() => onChange([])}
            >
              {locale === "zh-CN" ? "清空" : "Clear"}
            </button>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
