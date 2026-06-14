import type { ProtocolKind } from "@/lib/api";

export const PROTOCOL_LIST: ProtocolKind[] = [
  "openai_chat",
  "openai_responses",
  "openai_embedding",
  "openai_image",
  "rerank",
  "anthropic",
  "gemini",
];

export const PROTOCOL_LABELS: Record<ProtocolKind, { zh: string; en: string }> =
  {
    openai_chat: { zh: "OpenAI Chat", en: "OpenAI Chat" },
    openai_responses: { zh: "OpenAI Responses", en: "OpenAI Responses" },
    openai_embedding: { zh: "OpenAI Embedding", en: "OpenAI Embedding" },
    openai_image: { zh: "OpenAI Image", en: "OpenAI Image" },
    rerank: { zh: "Rerank", en: "Rerank" },
    anthropic: { zh: "Anthropic", en: "Anthropic" },
    gemini: { zh: "Gemini", en: "Gemini" },
  };

export function compactProtocolLabel(protocol: ProtocolKind): string {
  switch (protocol) {
    case "openai_chat":
      return "chat";
    case "openai_responses":
      return "responses";
    case "openai_embedding":
      return "embeddings";
    case "openai_image":
      return "image";
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

export function protocolLabel(
  protocol: ProtocolKind,
  locale: "zh-CN" | "en-US",
): string {
  return PROTOCOL_LABELS[protocol][locale === "zh-CN" ? "zh" : "en"];
}

export function protocolOptions(locale: "zh-CN" | "en-US") {
  return PROTOCOL_LIST.map((value) => ({
    value,
    label: protocolLabel(value, locale),
  }));
}

export function protocolBadgeClassName(protocol: ProtocolKind) {
  switch (protocol) {
    case "openai_chat":
      return "border-transparent bg-sky-500/10 text-sky-700";
    case "openai_responses":
      return "border-transparent bg-indigo-500/10 text-indigo-700";
    case "openai_embedding":
      return "border-transparent bg-cyan-500/10 text-cyan-700";
    case "openai_image":
      return "border-transparent bg-rose-500/10 text-rose-700";
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

export const PROTOCOL_DOT_CLASS: Record<ProtocolKind, string> = {
  openai_chat: "bg-sky-500",
  openai_responses: "bg-indigo-500",
  openai_embedding: "bg-muted-foreground/60",
  openai_image: "bg-rose-500",
  rerank: "bg-muted-foreground/60",
  anthropic: "bg-amber-500",
  gemini: "bg-emerald-500",
};
