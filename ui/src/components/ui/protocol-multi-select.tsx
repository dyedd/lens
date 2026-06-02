"use client";

import { type JSX } from "react";
import { ChevronDown } from "lucide-react";

import { type ProtocolKind } from "@/lib/api";
import { cn } from "@/lib/utils";
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
}

const CHAT_PROTOCOLS: ProtocolKind[] = [
  "openai_chat",
  "openai_responses",
  "anthropic",
  "gemini",
];

const SPECIAL_PROTOCOLS: ProtocolKind[] = ["openai_embedding", "rerank"];

const ALL_PROTOCOLS: ProtocolKind[] = [...CHAT_PROTOCOLS, ...SPECIAL_PROTOCOLS];

const PROTOCOL_DOT_CLASS: Record<ProtocolKind, string> = {
  openai_chat: "bg-sky-500",
  openai_responses: "bg-indigo-500",
  anthropic: "bg-amber-500",
  gemini: "bg-emerald-500",
  openai_embedding: "bg-muted-foreground/60",
  rerank: "bg-muted-foreground/60",
};

function protocolLabel(protocol: ProtocolKind): string {
  switch (protocol) {
    case "openai_chat":
      return "chat";
    case "openai_responses":
      return "responses";
    case "openai_embedding":
      return "embeddings";
    case "rerank":
      return "rerank";
    case "anthropic":
      return "anthropic";
    case "gemini":
      return "gemini";
    default:
      return protocol;
  }
}

const COPY = {
  "zh-CN": {
    placeholder: "选择协议",
    chat: "聊天协议",
    special: "特殊协议",
    summarySuffix: (n: number) => `共 ${n} 项`,
  },
  "en-US": {
    placeholder: "Select protocols",
    chat: "Chat",
    special: "Special",
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
                {protocolLabel(protocol)}
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
}: ProtocolMultiSelectProps): JSX.Element {
  const allowed = allowedProtocols ?? ALL_PROTOCOLS;
  const chatProtocols = CHAT_PROTOCOLS.filter((p) => allowed.includes(p));
  const specialProtocols = SPECIAL_PROTOCOLS.filter((p) => allowed.includes(p));
  const copy = COPY[locale];

  const toggle = (protocol: ProtocolKind) => {
    onChange(
      value.includes(protocol)
        ? value.filter((p) => p !== protocol)
        : [...value, protocol],
    );
  };

  const selectedInOrder = ALL_PROTOCOLS.filter((p) => value.includes(p));
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
            <span className="truncate">{copy.placeholder}</span>
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
                  {protocolLabel(protocol)}
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
          label={copy.chat}
          protocols={chatProtocols}
          value={value}
          onToggle={toggle}
          disabled={disabled}
        />
        {chatProtocols.length > 0 && specialProtocols.length > 0 ? (
          <div className="h-px bg-border" />
        ) : null}
        <ProtocolGroup
          label={copy.special}
          protocols={specialProtocols}
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
