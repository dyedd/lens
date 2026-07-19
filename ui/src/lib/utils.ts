import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Combines conditional class names while resolving Tailwind conflicts. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Reports whether a credential name matches an automatically generated label. */
export function isGeneratedCredentialName(value: string) {
  const normalized = value.trim().toLowerCase();
  return (
    normalized === "默认密钥" ||
    /^key\s*\d+$/.test(normalized) ||
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
