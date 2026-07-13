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
