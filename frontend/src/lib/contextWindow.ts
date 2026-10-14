/** Context window helpers mirroring backend/app/core/context_windows.py. */

export const MIN_CONTEXT_WINDOW = 1_000;
export const MAX_CONTEXT_WINDOW = 100_000_000;

export type ContextWindowSource = "manual" | "upstream" | "model_name";

/** Shorter name suffixes such as "-4k" usually describe image resolution. */
const MIN_MODEL_NAME_CONTEXT_WINDOW = 8_000;
const MODEL_NAME_CONTEXT_RE =
  /(?:^|[-_/:@[(\s])(\d+(?:\.\d+)?)([km])(?=$|[-_/:.\])\s])/gi;
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

/** Reads the context size a model name advertises, e.g. "glm-4.6-200k". */
export function parseModelNameContextWindow(modelName: string): number | null {
  let size: number | null = null;
  for (const match of modelName.matchAll(MODEL_NAME_CONTEXT_RE)) {
    const tokens = Math.round(
      Number(match[1]) * UNIT_TOKENS[match[2].toLowerCase()],
    );
    if (
      isSupportedContextWindow(tokens) &&
      tokens >= MIN_MODEL_NAME_CONTEXT_WINDOW
    ) {
      size = tokens;
    }
  }
  return size;
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
  if (source === "upstream")
    return isZh ? "上游模型列表" : "Upstream model list";
  return isZh ? "模型名识别" : "Detected from model name";
}
