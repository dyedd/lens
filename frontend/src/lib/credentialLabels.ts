/** Reports whether a credential name is an automatically generated label. */
export function isGeneratedCredentialName(value: string) {
  const lowerValue = value.trim().toLowerCase();
  return (
    lowerValue === "默认密钥" ||
    /^key\s*\d+$/.test(lowerValue) ||
    /^密钥\s*\d+$/.test(value.trim())
  );
}

function generatedCredentialNumber(value: string) {
  const match = value.trim().match(/^(?:key|密钥)\s*(\d+)$/i);
  if (!match) return 0;
  const number = Number(match[1]);
  return Number.isSafeInteger(number) && number > 0 ? number : 0;
}

/** Returns a credential remark or its localized positional fallback. */
export function formatCredentialDisplayName(
  value: string | undefined,
  number: number,
  locale: string,
) {
  const name = value?.trim() ?? "";
  if (name && !isGeneratedCredentialName(name)) return name;
  const position = number > 0 ? number : generatedCredentialNumber(name) || 1;
  return locale === "zh-CN" ? `密钥 ${position}` : `Key ${position}`;
}

/** Builds the fallback persisted name for a credential. */
export function fallbackCredentialName(index: number) {
  return `Key ${index + 1}`;
}

/** Returns a credential name or its localized positional fallback. */
export function credentialLabel(
  item: { name: string },
  index: number,
  locale: string,
) {
  return formatCredentialDisplayName(item.name, index + 1, locale);
}

/** Formats a key as its label plus masked value for selectors and tooltips. */
export function formatCredentialTitle(
  item: { name: string; api_key: string },
  index: number,
  locale: string,
) {
  return `${credentialLabel(item, index, locale)} · ${maskApiKey(item.api_key)}`;
}

/** Masks a stored API key for the existing-key list. */
function maskApiKey(value: string) {
  const key = value.trim();
  if (key.length <= 8) return "••••";
  return `${key.slice(0, Math.min(4, key.length - 4))}****${key.slice(-4)}`;
}
