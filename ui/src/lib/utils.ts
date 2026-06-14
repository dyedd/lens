import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function isGeneratedCredentialName(value: string) {
  const normalized = value.trim().toLowerCase();
  return (
    normalized === "默认密钥" ||
    /^key\s*\d+$/.test(normalized) ||
    /^密钥\s*\d+$/.test(value.trim())
  );
}
