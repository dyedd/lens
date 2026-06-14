"use client";

import { type JSX } from "react";
import { ChevronDown } from "lucide-react";

import { type ProtocolKind } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  PROTOCOL_LIST,
  PROTOCOL_DOT_CLASS,
  compactProtocolLabel,
} from "@/lib/protocols";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

export interface ProtocolMultiSelectProps {
  value: ProtocolKind[];
  onChange: (next: ProtocolKind[]) => void;
  locale: "zh-CN" | "en-US";
  className?: string;
  allowedProtocols?: ProtocolKind[];
  disabled?: boolean;
  invalid?: boolean;
  requireAtLeastOne?: boolean;
  placeholder?: string;
}

const COPY = {
  "zh-CN": {
    placeholder: "选择客户端协议",
    client: "客户端协议",
    summarySuffix: (n: number) => `共 ${n} 项`,
  },
  "en-US": {
    placeholder: "Select client protocols",
    client: "Client protocols",
    summarySuffix: (n: number) => `${n} selected`,
  },
} as const;

interface ProtocolGroupProps {
  label: string;
  protocols: ProtocolKind[];
  value: ProtocolKind[];
  onToggle: (protocol: ProtocolKind) => void;
  disabled: boolean;
}

function ProtocolGroup({
  label,
  protocols,
  value,
  onToggle,
  disabled,
}: ProtocolGroupProps): JSX.Element | null {
  if (protocols.length === 0) return null;

  return (
    <div className="flex flex-col gap-1">
      <div className="px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="grid grid-cols-2 gap-0.5">
        {protocols.map((protocol) => {
          const checked = value.includes(protocol);
          const checkboxId = `protocol-opt-${protocol}`;
          return (
            <div
              key={protocol}
              className={cn(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted",
                disabled &&
                  "cursor-not-allowed opacity-50 hover:bg-transparent",
              )}
            >
              <Checkbox
                id={checkboxId}
                checked={checked}
                onCheckedChange={() => !disabled && onToggle(protocol)}
                disabled={disabled}
              />
              <span
                className={cn(
                  "size-1.5 shrink-0 rounded-full",
                  PROTOCOL_DOT_CLASS[protocol],
                )}
              />
              <label
                htmlFor={checkboxId}
                className={cn(
                  "truncate cursor-pointer",
                  disabled && "cursor-not-allowed",
                )}
              >
                {compactProtocolLabel(protocol)}
              </label>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ProtocolMultiSelect({
  value,
  onChange,
  locale,
  className,
  allowedProtocols,
  disabled = false,
  invalid = false,
  requireAtLeastOne = false,
  placeholder,
}: ProtocolMultiSelectProps): JSX.Element {
  const allowed = allowedProtocols ?? PROTOCOL_LIST;
  const clientProtocols = PROTOCOL_LIST.filter((p) => allowed.includes(p));
  const copy = COPY[locale];

  const toggle = (protocol: ProtocolKind) => {
    onChange(
      value.includes(protocol)
        ? value.filter((p) => p !== protocol)
        : [...value, protocol],
    );
  };

  const selectedInOrder = PROTOCOL_LIST.filter((p) => value.includes(p));
  const clearDisabled = requireAtLeastOne && value.length <= 1;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          aria-invalid={invalid || undefined}
          className={cn(
            "w-full justify-between px-3 font-normal",
            selectedInOrder.length === 0 && "text-muted-foreground",
            className,
          )}
        >
          {selectedInOrder.length === 0 ? (
            <span className="truncate">{placeholder ?? copy.placeholder}</span>
          ) : (
            <span className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden">
              {selectedInOrder.slice(0, 3).map((protocol) => (
                <span
                  key={protocol}
                  className="flex shrink-0 items-center gap-1 text-xs text-foreground"
                >
                  <span
                    className={cn(
                      "size-1.5 rounded-full",
                      PROTOCOL_DOT_CLASS[protocol],
                    )}
                  />
                  {compactProtocolLabel(protocol)}
                </span>
              ))}
              {selectedInOrder.length > 3 ? (
                <span className="shrink-0 text-xs text-muted-foreground">
                  +{selectedInOrder.length - 3}
                </span>
              ) : null}
            </span>
          )}
          <ChevronDown className="ml-1 size-3.5 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[21rem] gap-3 p-3">
        <ProtocolGroup
          label={copy.client}
          protocols={clientProtocols}
          value={value}
          onToggle={toggle}
          disabled={disabled}
        />
        {value.length > 0 ? (
          <div className="flex items-center justify-between border-t pt-2 text-xs text-muted-foreground">
            <span>{copy.summarySuffix(value.length)}</span>
            <button
              type="button"
              disabled={clearDisabled}
              className={cn(
                "text-foreground hover:underline",
                clearDisabled &&
                  "cursor-not-allowed opacity-50 hover:no-underline",
              )}
              onClick={() => {
                if (clearDisabled) return;
                onChange([]);
              }}
            >
              {locale === "zh-CN" ? "清空" : "Clear"}
            </button>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
