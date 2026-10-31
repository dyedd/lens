/** Context window helpers mirroring backend/app/core/context_windows.py. */

export const MIN_CONTEXT_WINDOW = 1_000;
export const MAX_CONTEXT_WINDOW = 100_000_000;

export type ContextWindowSource = "manual" | "upstream";

const CONTEXT_INPUT_RE = /^(\d+(?:\.\d+)?)\s*([km])?$/i;
const UNIT_TOKENS: Record<string, number> = { k: 1_000, m: 1_000_000 };

function isSupportedContextWindow(value: number) {
  return (
    Number.isInteger(value) &&
    value >= MIN_CONTEXT_WINDOW &&
    value <= MAX_CONTEXT_WINDOW
  );
}

/**
 * Parses an admin-entered size such as "200K", "1M" or "128000".
 * Returns null for an empty value and undefined when the text is invalid.
 */
export function parseContextWindowInput(
  text: string,
): number | null | undefined {
  const value = text.trim().replaceAll(",", "").replaceAll("_", "");
  if (!value) return null;
  const match = CONTEXT_INPUT_RE.exec(value);
  if (!match) return undefined;
  const unit = match[2]?.toLowerCase();
  const tokens = Math.round(Number(match[1]) * (unit ? UNIT_TOKENS[unit] : 1));
  return isSupportedContextWindow(tokens) ? tokens : undefined;
}

/** Formats a token count compactly: 1000000 → "1M", 131072 → "128K". */
export function formatContextWindow(tokens: number): string {
  if (tokens % 1_000_000 === 0) return `${tokens / 1_000_000}M`;
  if (tokens % 1_048_576 === 0) return `${tokens / 1_048_576}M`;
  if (tokens % 1_000 === 0) return `${tokens / 1_000}K`;
  if (tokens % 1_024 === 0) return `${tokens / 1_024}K`;
  if (tokens >= 1_000_000) return `${Number((tokens / 1_000_000).toFixed(2))}M`;
  return `${Number((tokens / 1_000).toFixed(1))}K`;
}

/** Labels where a resolved context window came from. */
export function contextWindowSourceLabel(
  source: ContextWindowSource,
  locale: string,
): string {
  const isZh = locale === "zh-CN";
  if (source === "manual") return isZh ? "手动设置" : "Set manually";
  return isZh ? "上游模型列表" : "Upstream model list";
}

/**
 * Estimates a common model's context window for UI suggestions when the
 * upstream reports nothing. This never alters routing on its own.
 */
export function estimateContextWindow(modelName: string): number | null {
  const name = modelName.toLowerCase().trim();
  if (!name) return null;

  // 1. Explicit size hints in the model name (e.g. "moonshot-v1-128k", "model-32k", "deepseek-64k")
  const suffixMatch = /[-_:]([0-9]+(?:\.[0-9]+)?)([km])\b/i.exec(name);
  if (suffixMatch) {
    const num = Number(suffixMatch[1]);
    const unit = suffixMatch[2].toLowerCase();
    const tokens = Math.round(num * (unit === "m" ? 1_000_000 : 1_000));
    if (isSupportedContextWindow(tokens)) return tokens;
  }

  // 2. Mainstream model family lookups
  if (name.includes("gemini-1.5-pro") || name.includes("gemini-2.5-pro")) {
    return 2_000_000;
  }
  if (name.includes("gemini")) return 1_000_000;
  if (
    name.includes("claude-3") ||
    name.includes("claude-sonnet") ||
    name.includes("claude-opus") ||
    name.includes("claude-haiku")
  ) {
    return 200_000;
  }
  if (
    name.includes("o1") ||
    name.includes("o3") ||
    name.includes("gpt-4o") ||
    name.includes("gpt-4-turbo")
  ) {
    return 128_000;
  }
  if (name.includes("deepseek")) return 64_000;
  if (
    name.includes("llama-3.1") ||
    name.includes("llama-3.2") ||
    name.includes("llama-3.3")
  ) {
    return 128_000;
  }
  if (name.includes("qwen-2.5")) return 128_000;
  if (name.includes("qwen")) return 32_768;
  if (name.includes("gpt-3.5")) return 16_384;
  if (name.includes("gpt-4")) return 8_192;

  return null;
}
