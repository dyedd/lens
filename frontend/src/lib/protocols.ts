import type { ProtocolKind } from "@/lib/api/protocols";

export const PROTOCOL_LIST: ProtocolKind[] = [
  "openai_chat",
  "openai_responses",
  "openai_embedding",
  "openai_image",
  "rerank",
  "anthropic",
  "gemini",
];

const PROTOCOL_LABELS: Record<ProtocolKind, { zh: string; en: string }> = {
  auto: { zh: "Auto", en: "Auto" },
  openai_chat: { zh: "OpenAI Chat", en: "OpenAI Chat" },
  openai_responses: { zh: "OpenAI Responses", en: "OpenAI Responses" },
  openai_embedding: { zh: "OpenAI Embedding", en: "OpenAI Embedding" },
  openai_image: { zh: "OpenAI Image", en: "OpenAI Image" },
  rerank: { zh: "Rerank", en: "Rerank" },
  anthropic: { zh: "Anthropic", en: "Anthropic" },
  gemini: { zh: "Gemini", en: "Gemini" },
};

/** Returns the localized display label for a protocol. */
export function protocolLabel(
  protocol: ProtocolKind,
  locale: "zh-CN" | "en-US",
): string {
  return PROTOCOL_LABELS[protocol][locale === "zh-CN" ? "zh" : "en"];
}

/** Builds localized protocol selection options. */
export function protocolOptions(locale: "zh-CN" | "en-US") {
  return PROTOCOL_LIST.map((value) => ({
    value,
    label: protocolLabel(value, locale),
  }));
}
