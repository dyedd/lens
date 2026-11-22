export type ProtocolKind =
  | "openai_chat"
  | "openai_responses"
  | "openai_embedding"
  | "openai_image"
  | "rerank"
  | "anthropic"
  | "gemini";

export function isProtocolKind(value: unknown): value is ProtocolKind {
  return (
    value === "openai_chat" ||
    value === "openai_responses" ||
    value === "openai_embedding" ||
    value === "openai_image" ||
    value === "rerank" ||
    value === "anthropic" ||
    value === "gemini"
  );
}
