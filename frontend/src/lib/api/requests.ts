import { ApiError, apiRequest, isRecord } from "./client";
import { isProtocolKind, type ProtocolKind } from "./protocols";

export type RequestLogLifecycleStatus =
  | "connecting"
  | "streaming"
  | "succeeded"
  | "failed"
  | "cancelled";
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
  can_cancel: boolean;
  is_stream: boolean;
  first_token_latency_ms: number;
  latency_ms: number;
  input_tokens: number;
  image_input_tokens: number;
  cache_read_input_tokens: number;
  cache_write_input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_cost_usd: number;
  output_cost_usd: number;
  total_cost_usd: number;
  rate_multiplier: number | null;
  billing_mode: "free" | "tokens" | "non_tokens";
  billing_units: number;
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

function isOptionalString(value: unknown) {
  return value == null || typeof value === "string";
}

function isRequestLogItem(value: unknown): value is RequestLogItem {
  if (!isRecord(value)) return false;
  return (
    isProtocolKind(value.protocol) &&
    (value.lifecycle_status === "connecting" ||
      value.lifecycle_status === "streaming" ||
      value.lifecycle_status === "succeeded" ||
      value.lifecycle_status === "failed" ||
      value.lifecycle_status === "cancelled") &&
    (value.billing_mode === "free" ||
      value.billing_mode === "tokens" ||
      value.billing_mode === "non_tokens") &&
    typeof value.user_agent === "string" &&
    typeof value.credential_name === "string" &&
    typeof value.created_at === "string" &&
    typeof value.success === "boolean" &&
    typeof value.can_cancel === "boolean" &&
    typeof value.is_stream === "boolean" &&
    typeof value.channel_has_multiple_credentials === "boolean" &&
    typeof value.gateway_has_multiple_keys === "boolean" &&
    (value.rate_multiplier === null ||
      Number.isFinite(value.rate_multiplier)) &&
    (value.status_code == null || Number.isFinite(value.status_code)) &&
    Number.isFinite(value.id) &&
    Number.isFinite(value.credential_number) &&
    Number.isFinite(value.first_token_latency_ms) &&
    Number.isFinite(value.latency_ms) &&
    Number.isFinite(value.input_tokens) &&
    Number.isFinite(value.image_input_tokens) &&
    Number.isFinite(value.cache_read_input_tokens) &&
    Number.isFinite(value.cache_write_input_tokens) &&
    Number.isFinite(value.output_tokens) &&
    Number.isFinite(value.total_tokens) &&
    Number.isFinite(value.input_cost_usd) &&
    Number.isFinite(value.output_cost_usd) &&
    Number.isFinite(value.total_cost_usd) &&
    Number.isFinite(value.billing_units) &&
    Number.isFinite(value.attempt_count) &&
    isOptionalString(value.requested_group_name) &&
    isOptionalString(value.resolved_group_name) &&
    isOptionalString(value.upstream_model_name) &&
    isOptionalString(value.channel_id) &&
    isOptionalString(value.channel_name) &&
    isOptionalString(value.credential_id) &&
    isOptionalString(value.gateway_key_id) &&
    isOptionalString(value.gateway_key_remark) &&
    isOptionalString(value.reasoning_effort) &&
    isOptionalString(value.error_message)
  );
}

function isRequestLogAttempt(value: unknown): value is RequestLogAttempt {
  return (
    isRecord(value) &&
    typeof value.channel_id === "string" &&
    typeof value.channel_name === "string" &&
    typeof value.credential_name === "string" &&
    typeof value.channel_has_multiple_credentials === "boolean" &&
    typeof value.success === "boolean" &&
    Number.isFinite(value.credential_number) &&
    Number.isFinite(value.duration_ms) &&
    (value.status_code == null || Number.isFinite(value.status_code)) &&
    isOptionalString(value.credential_id) &&
    isOptionalString(value.model_name) &&
    isOptionalString(value.error_message) &&
    isOptionalString(value.reasoning_effort)
  );
}

function isFilterOption(value: unknown): value is RequestLogFilterOption {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.label === "string"
  );
}

function isRequestLogPage(value: unknown): value is RequestLogPage {
  return (
    isRecord(value) &&
    Array.isArray(value.items) &&
    value.items.every(isRequestLogItem) &&
    Number.isFinite(value.total) &&
    Number.isFinite(value.limit) &&
    Number.isFinite(value.offset) &&
    Array.isArray(value.channels) &&
    value.channels.every(isFilterOption) &&
    Array.isArray(value.gateway_keys) &&
    value.gateway_keys.every(isFilterOption) &&
    typeof value.gateway_has_multiple_keys === "boolean" &&
    Array.isArray(value.model_names) &&
    value.model_names.every((name) => typeof name === "string")
  );
}

function isRequestLogDetail(value: unknown): value is RequestLogDetail {
  return (
    isRecord(value) &&
    Array.isArray(value.attempts) &&
    value.attempts.every(isRequestLogAttempt) &&
    isOptionalString(value.request_content) &&
    isOptionalString(value.response_content) &&
    isRequestLogItem(value)
  );
}

export async function requestLogPage(
  params: URLSearchParams,
): Promise<RequestLogPage> {
  const value = await apiRequest<unknown>(
    `/admin/request-logs/page?${params.toString()}`,
  );
  if (!isRequestLogPage(value)) {
    throw new ApiError("Invalid request log page response from API", 200);
  }
  return value;
}

export async function requestLogDetail(id: number): Promise<RequestLogDetail> {
  const value = await apiRequest<unknown>(`/admin/request-logs/${id}`);
  if (!isRequestLogDetail(value)) {
    throw new ApiError("Invalid request log detail response from API", 200);
  }
  return value;
}
