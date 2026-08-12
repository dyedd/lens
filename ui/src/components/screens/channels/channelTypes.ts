import type {
  ChannelProxyMode,
  ProtocolKind,
  Site,
  SiteBaseUrlInput,
  SiteCredentialInput,
  SiteModelInput,
} from "@/lib/api";
import type { Locale } from "@/lib/I18nContext";
import type { BatchModelTestSource } from "../batchModelTestSession";

export type HeaderItem = { key: string; value: string };
export type FormCredential = Omit<SiteCredentialInput, "id"> & { id: string };
export type FormBaseUrl = Omit<SiteBaseUrlInput, "id"> & {
  id: string;
  supported_protocols: ProtocolKind[];
};
export type { Locale };

export type FormModel = Omit<SiteModelInput, "id" | "protocol"> & {
  protocols: ProtocolKind[];
  protocolIds: Partial<Record<ProtocolKind, string>>;
};

export type FormProtocolConfig = {
  id: string;
  name: string;
  enabled: boolean;
  headers: HeaderItem[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  param_override: string;
  model_filter: string;
  sync_new_models: boolean;
  manual_model_name: string;
  manual_protocols: ProtocolKind[];
  base_url_id: string;
  credential_ids: string[];
  sync_targets: FormSyncTarget[];
  models: FormModel[];
  expanded: boolean;
};

export type FormSyncTarget = {
  credential_id: string;
  model_name: string;
  protocol: ProtocolKind;
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

export type TestableModelOption = BatchModelTestSource<ModelTestTarget>;

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

export type ModelQueryInputKind = "empty" | "plain" | "regex";
