"use client";

import { type JSX } from "react";

import { type ProtocolKind } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";

export interface ProtocolMultiSelectProps {
  value: ProtocolKind[];
  onChange: (next: ProtocolKind[]) => void;
  locale: "zh-CN" | "en-US";
  className?: string;
  allowedProtocols?: ProtocolKind[];
  disabled?: boolean;
}

const CHAT_PROTOCOLS: ProtocolKind[] = [
  "openai_chat",
  "openai_responses",
  "anthropic",
  "gemini",
];

const SPECIAL_PROTOCOLS: ProtocolKind[] = [
  "openai_embedding",
  "rerank",
];

const ALL_PROTOCOLS: ProtocolKind[] = [...CHAT_PROTOCOLS, ...SPECIAL_PROTOCOLS];

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

function chatToggleClassName(protocol: ProtocolKind): string {
  switch (protocol) {
    case "openai_chat":
      return "data-[state=on]:border-sky-500/40 data-[state=on]:bg-sky-500/10 data-[state=on]:text-sky-700";
    case "openai_responses":
      return "data-[state=on]:border-indigo-500/40 data-[state=on]:bg-indigo-500/10 data-[state=on]:text-indigo-700";
    case "anthropic":
      return "data-[state=on]:border-amber-500/40 data-[state=on]:bg-amber-500/10 data-[state=on]:text-amber-700";
    case "gemini":
      return "data-[state=on]:border-emerald-500/40 data-[state=on]:bg-emerald-500/10 data-[state=on]:text-emerald-700";
    default:
      return "";
  }
}

const SPECIAL_TOGGLE_CLASS =
  "data-[state=on]:border-muted-foreground/30 data-[state=on]:bg-muted data-[state=on]:text-foreground";

const COPY = {
  "zh-CN": {
    ariaLabel: "选择协议",
    chat: "聊天协议",
    special: "特殊协议",
  },
  "en-US": {
    ariaLabel: "Select protocols",
    chat: "Chat",
    special: "Special",
  },
} as const;

interface ProtocolRowProps {
  label: string;
  protocols: ProtocolKind[];
  value: ProtocolKind[];
  onChange: (next: ProtocolKind[]) => void;
  ariaLabel: string;
  disabled: boolean;
  toggleClassName: (protocol: ProtocolKind) => string;
  size?: "default" | "compact";
}

function ProtocolRow({
  label,
  protocols,
  value,
  onChange,
  ariaLabel,
  disabled,
  toggleClassName,
  size = "default",
}: ProtocolRowProps): JSX.Element | null {
  if (protocols.length === 0) return null;

  const selectedInRow = value.filter((v) => protocols.includes(v));

  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <span className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/80">
        {label}
      </span>
      <ToggleGroup
        type="multiple"
        value={selectedInRow}
        onValueChange={(next) => {
          const others = value.filter((v) => !protocols.includes(v));
          onChange([...others, ...(next as ProtocolKind[])]);
        }}
        disabled={disabled}
        aria-label={ariaLabel}
        className="flex flex-wrap justify-start gap-1"
      >
        {protocols.map((protocol) => (
          <ToggleGroupItem
            key={protocol}
            value={protocol}
            disabled={disabled}
            className={cn(
              "rounded-full border px-3 text-xs transition-colors",
              size === "compact" ? "h-6" : "h-7",
              toggleClassName(protocol),
            )}
          >
            {protocolLabel(protocol)}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
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
}: ProtocolMultiSelectProps): JSX.Element {
  const allowed = allowedProtocols ?? ALL_PROTOCOLS;
  const chatProtocols = CHAT_PROTOCOLS.filter((p) => allowed.includes(p));
  const specialProtocols = SPECIAL_PROTOCOLS.filter((p) => allowed.includes(p));
  const copy = COPY[locale];

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <ProtocolRow
        label={copy.chat}
        protocols={chatProtocols}
        value={value}
        onChange={onChange}
        ariaLabel={copy.ariaLabel}
        disabled={disabled}
        toggleClassName={chatToggleClassName}
      />
      <ProtocolRow
        label={copy.special}
        protocols={specialProtocols}
        value={value}
        onChange={onChange}
        ariaLabel={copy.ariaLabel}
        disabled={disabled}
        toggleClassName={() => SPECIAL_TOGGLE_CLASS}
        size="compact"
      />
    </div>
  );
}
