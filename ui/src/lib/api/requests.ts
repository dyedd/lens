import type { ProtocolKind } from "./protocols";
export type RequestLogLifecycleStatus =
  | "connecting"
  | "streaming"
  | "succeeded"
  | "failed";
export type RequestLogAttempt = {
  channel_id: string;
  channel_name: string;
  credential_id?: string | null;
  credential_name: string;
  credential_number: number;
  channel_has_multiple_credentials: boolean;
  model_name?: string | null;
  status_code?: number | null;
  success: boolean;
  duration_ms: number;
  error_message?: string | null;
  reasoning_effort?: string | null;
};
export type RequestLogItem = {
  id: number;
  protocol: ProtocolKind;
  user_agent: string;
  requested_group_name?: string | null;
  resolved_group_name?: string | null;
  upstream_model_name?: string | null;
  channel_id?: string | null;
  channel_name?: string | null;
  credential_id?: string | null;
  credential_name: string;
  credential_number: number;
  channel_has_multiple_credentials: boolean;
  gateway_key_id?: string | null;
  gateway_key_remark?: string | null;
  gateway_has_multiple_keys: boolean;
  reasoning_effort?: string | null;
  status_code?: number | null;
  success: boolean;
  lifecycle_status: RequestLogLifecycleStatus;
  is_stream: boolean;
  first_token_latency_ms: number;
  latency_ms: number;
  input_tokens: number;
  cache_read_input_tokens: number;
  cache_write_input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_cost_usd: number;
  output_cost_usd: number;
  total_cost_usd: number;
  attempt_count: number;
  error_message?: string | null;
  created_at: string;
};
export type RequestLogDetail = RequestLogItem & {
  request_content?: string | null;
  response_content?: string | null;
  attempts: RequestLogAttempt[];
};
export type RequestLogFilterOption = { id: string; label: string };
export type RequestLogPage = {
  items: RequestLogItem[];
  total: number;
  limit: number;
  offset: number;
  channels: RequestLogFilterOption[];
  gateway_keys: RequestLogFilterOption[];
  gateway_has_multiple_keys: boolean;
  model_names: string[];
};
