import type { ProtocolKind } from "./protocols";

export type RoutingStrategy = "round_robin" | "failover";
export type ModelGroupSyncFilterMode = "" | "contains" | "regex";
export type ModelGroupItem = {
  channel_id: string;
  channel_name: string;
  protocol?: ProtocolKind | null;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  model_name: string;
  enabled: boolean;
  sort_order: number;
};
export type ModelGroup = {
  id: string;
  name: string;
  protocols: ProtocolKind[];
  strategy: RoutingStrategy;
  route_group_id?: string;
  route_group_name?: string;
  sync_filter_mode: ModelGroupSyncFilterMode;
  sync_filter_query: string;
  input_price_per_million: number;
  output_price_per_million: number;
  cache_read_price_per_million: number;
  cache_write_price_per_million: number;
  items: ModelGroupItem[];
};
export type ModelGroupItemPayload = {
  channel_id: string;
  credential_id: string;
  model_name: string;
  enabled: boolean;
};
export type ModelGroupPayload = {
  name: string;
  protocols: ProtocolKind[];
  strategy: RoutingStrategy;
  route_group_id?: string;
  sync_filter_mode: ModelGroupSyncFilterMode;
  sync_filter_query: string;
  items: ModelGroupItemPayload[];
};
export type ModelGroupCandidateItem = {
  site_id: string;
  channel_id: string;
  channel_name: string;
  protocol: ProtocolKind;
  credential_id: string;
  credential_name: string;
  credential_number: number;
  base_url: string;
  model_name: string;
  protocol_config_id: string;
  protocols: ProtocolKind[];
  protocol_channels: Partial<Record<ProtocolKind, string>>;
  items: ModelGroupItemPayload[];
};
export type ModelGroupCandidatesPayload = {
  protocols?: ProtocolKind[];
  exclude_items: ModelGroupItemPayload[];
};
export type ModelGroupCandidatesResponse = {
  candidates: ModelGroupCandidateItem[];
};
export type ModelGroupEnsureStatus =
  | "create"
  | "update"
  | "unchanged"
  | "skipped";
export type ModelGroupEnsureModelInput = {
  protocol_config_id: string;
  credential_id: string;
  model_name: string;
  group_name?: string;
  protocols: ProtocolKind[];
};
export type ModelGroupEnsureFromSitePayload = {
  site_id: string;
  dry_run: boolean;
  allow_protocol_extension: boolean;
  models: ModelGroupEnsureModelInput[];
};
export type ModelGroupEnsureResultItem = {
  group_id: string;
  group_name: string;
  protocol_config_id: string;
  credential_id: string;
  model_name: string;
  protocols: ProtocolKind[];
  status: ModelGroupEnsureStatus;
  added_count: number;
  existing_count: number;
  skipped_reason: string;
  missing_protocols: ProtocolKind[];
};
export type ModelGroupEnsureFromSiteResponse = {
  dry_run: boolean;
  created_count: number;
  updated_count: number;
  unchanged_count: number;
  skipped_count: number;
  items: ModelGroupEnsureResultItem[];
};
export type ChannelModelSyncPayload = { dry_run: boolean };
export type ChannelModelSyncGroupChange = {
  group_name: string;
  model_name: string;
};
export type ChannelModelSyncResultItem = {
  protocol_config_id: string;
  channel_name: string;
  success: boolean;
  error: string;
  warning: string;
  added: string[];
  removed: string[];
  group_added: ChannelModelSyncGroupChange[];
};
export type ChannelModelSyncResponse = {
  dry_run: boolean;
  synced_channel_count: number;
  skipped_channel_count: number;
  items: ChannelModelSyncResultItem[];
};
