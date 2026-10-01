export function formatJson(value: string): string | null {
  if (!value.trim()) return "";
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return null;
  }
}
