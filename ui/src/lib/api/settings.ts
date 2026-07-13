export type SettingItem = { key: string; value: string };
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
  enabled: boolean;
  allowed_models: string[];
  max_cost_usd: number;
  expires_at?: string | null;
};
