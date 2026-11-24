import { ApiError, apiRequest } from "./client";

export type SettingItem = { key: string; value: string };

function isSettingItem(value: unknown): value is SettingItem {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    "key" in value &&
    typeof value.key === "string" &&
    "value" in value &&
    typeof value.value === "string"
  );
}

export async function requestSettings(
  init?: RequestInit,
): Promise<SettingItem[]> {
  const value = await apiRequest<unknown>("/admin/settings", init);
  if (!Array.isArray(value) || !value.every(isSettingItem)) {
    throw new ApiError("Invalid settings response from API", 200);
  }
  return value;
}
export type GatewayApiKey = {
  id: string;
  remark: string;
  api_key: string;
  enabled: boolean;
  allowed_models: string[];
  max_cost_usd: number;
  spent_cost_usd: number;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
};
export type GatewayApiKeyPayload = {
  remark: string;
  api_key?: string;
  enabled: boolean;
  allowed_models: string[];
  max_cost_usd: number;
  expires_at?: string | null;
};
