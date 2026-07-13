import type {
  ChannelProxyMode,
  ProtocolKind,
  Site,
  SiteBaseUrlInput,
  SiteCredentialInput,
  SiteModelInput,
} from "@/lib/api";
import type { Locale } from "@/lib/I18nContext";

export type HeaderItem = { key: string; value: string };
export type FormCredential = Omit<SiteCredentialInput, "id"> & { id: string };
export type FormBaseUrl = Omit<SiteBaseUrlInput, "id"> & {
  id: string;
  supported_protocols: ProtocolKind[];
};
export type { Locale };

export type FormModel = Omit<SiteModelInput, "protocol"> & {
  protocols: ProtocolKind[];
  protocolIds?: Record<string, string>;
};

export type FormProtocolConfig = {
  id?: string | null;
  name: string;
  enabled: boolean;
  headers: HeaderItem[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  param_override: string;
  match_regex: string;
  manual_model_name: string;
  manual_protocols: ProtocolKind[];
  base_url_id: string;
  credential_id: string;
  credential_ids: string[];
  auto_sync_enabled: boolean;
  models: FormModel[];
  expanded: boolean;
};

export type FormState = {
  name: string;
  base_urls: FormBaseUrl[];
  credentials: FormCredential[];
  protocolConfigs: FormProtocolConfig[];
};

export type PickerModelItem = {
  credential_id: string;
  credential_name?: string;
  model_name: string;
};

export type ModelTestTarget = {
  protocolConfigIndex: number;
  modelIndex: number;
};

export type BatchModelTestStatus = "pending" | "running" | "success" | "failed";

export type BatchModelTestRow = {
  key: string;
  modelName: string;
  credentialName: string;
  protocol: ProtocolKind;
  status: BatchModelTestStatus;
  statusCode?: number | null;
  latencyMs?: number;
  message: string;
};

export type BatchModelTestOption = {
  key: string;
  target: ModelTestTarget;
  modelName: string;
  credentialName: string;
  protocols: ProtocolKind[];
  selectedProtocol: ProtocolKind;
};

export type TestableModelOption = Omit<
  BatchModelTestOption,
  "selectedProtocol"
>;

export type SiteRow = Site & {
  subtitle: string;
  enabled_protocol_channel_count: number;
  model_count: number;
  endpoint_summary: string;
};

export type ChannelStatusFilter = "all" | "enabled" | "disabled";
export type ChannelSort =
  | "requests-desc"
  | "name-asc"
  | "name-desc"
  | "models-desc"
  | "protocols-desc";

export type ImportResultRow = {
  key: string;
  index: number;
  name: string;
  status: "created" | "skipped" | "error";
  reason: string;
};

export type ModelQueryInputKind = "empty" | "plain" | "regex";
