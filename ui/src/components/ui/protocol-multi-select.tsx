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

const protocolOptions: ProtocolKind[] = [
  "openai_chat",
  "openai_responses",
  "openai_embedding",
  "rerank",
  "anthropic",
  "gemini",
];

function compactProtocolLabel(protocol: ProtocolKind) {
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

function protocolToggleClassName(protocol: ProtocolKind) {
  switch (protocol) {
    case "openai_chat":
      return "data-[state=on]:border-transparent data-[state=on]:bg-sky-500/10 data-[state=on]:text-sky-700";
    case "openai_responses":
      return "data-[state=on]:border-transparent data-[state=on]:bg-indigo-500/10 data-[state=on]:text-indigo-700";
    case "openai_embedding":
      return "data-[state=on]:border-transparent data-[state=on]:bg-cyan-500/10 data-[state=on]:text-cyan-700";
    case "rerank":
      return "data-[state=on]:border-transparent data-[state=on]:bg-violet-500/10 data-[state=on]:text-violet-700";
    case "anthropic":
      return "data-[state=on]:border-transparent data-[state=on]:bg-amber-500/10 data-[state=on]:text-amber-700";
    case "gemini":
      return "data-[state=on]:border-transparent data-[state=on]:bg-emerald-500/10 data-[state=on]:text-emerald-700";
    default:
      return "data-[state=on]:border-transparent data-[state=on]:bg-secondary data-[state=on]:text-secondary-foreground";
  }
}

export function ProtocolMultiSelect({
  value,
  onChange,
  locale,
  className,
  allowedProtocols,
  disabled = false,
}: ProtocolMultiSelectProps): JSX.Element {
  const protocols = allowedProtocols ?? protocolOptions;

  return (
    <ToggleGroup
      type="multiple"
      value={value}
      onValueChange={(next) => onChange(next as ProtocolKind[])}
      disabled={disabled}
      aria-label={locale === "zh-CN" ? "选择协议" : "Select protocols"}
      className={cn("flex flex-wrap justify-start gap-1", className)}
    >
      {protocols.map((protocol) => (
        <ToggleGroupItem
          key={protocol}
          value={protocol}
          disabled={disabled}
          className={cn(
            "h-7 rounded-full border px-3 text-xs",
            protocolToggleClassName(protocol),
          )}
        >
          {compactProtocolLabel(protocol)}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
