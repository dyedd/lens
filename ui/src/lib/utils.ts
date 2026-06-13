import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import type { ProtocolKind } from "@/lib/api";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function protocolBadgeClassName(protocol: ProtocolKind) {
  switch (protocol) {
    case "openai_chat":
      return "border-transparent bg-sky-500/10 text-sky-700";
    case "openai_responses":
      return "border-transparent bg-indigo-500/10 text-indigo-700";
    case "openai_embedding":
      return "border-transparent bg-cyan-500/10 text-cyan-700";
    case "rerank":
      return "border-transparent bg-violet-500/10 text-violet-700";
    case "anthropic":
      return "border-transparent bg-amber-500/10 text-amber-700";
    case "gemini":
      return "border-transparent bg-emerald-500/10 text-emerald-700";
    default:
      return "border-transparent bg-secondary text-secondary-foreground";
  }
}

export function isGeneratedCredentialName(value: string) {
  const normalized = value.trim().toLowerCase();
  return (
    normalized === "默认密钥" ||
    /^key\s*\d+$/.test(normalized) ||
    /^密钥\s*\d+$/.test(value.trim())
  );
}
