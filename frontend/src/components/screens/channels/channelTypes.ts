import type { BatchModelTestSource } from "@/components/model-test/batchModelTestSession";
import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  ChannelProxyMode,
  Site,
  SiteCredential,
  SiteModelInput,
  SiteModelSyncSettings,
} from "@/lib/api/sites";
import type { Locale } from "@/lib/I18nContext";

export type FormCredential = Omit<
  SiteCredential,
  "sort_order" | "base_url_id"
> & {
  baseUrlId: string;
};
export type FormBaseUrl = {
  id: string;
  url: string;
  shareKeys: boolean;
  newApiKeysLines: string;
};
export type { Locale };

export type FormModel = Omit<SiteModelInput, "id" | "protocol"> & {
  protocols: ProtocolKind[];
  protocolIds: Partial<Record<ProtocolKind, string>>;
};

export type FormProtocolConfig = {
  id: string;
  base_url_id: string;
  credential_ids: string[];
  protocols: ProtocolKind[];
  models: FormModel[];
};

export type FormState = SiteModelSyncSettings & {
  name: string;
  tags: string[];
  newApiKeysLines: string;
  base_urls: FormBaseUrl[];
  credentials: FormCredential[];
  protocolConfigs: FormProtocolConfig[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  headersJson: string;
  paramsJson: string;
};

export type PickerModelItem = {
  protocol_config_id: string;
  credential_id: string;
  model_name: string;
};

export type ModelTestTarget = {
  protocolConfigIndex: number;
  modelIndex: number;
};

export type TestableModelOption = BatchModelTestSource<ModelTestTarget>;

export type SiteRow = Site & {
  model_count: number;
  endpoint_summary: string;
};

export type ChannelStatusFilter = "all" | "enabled" | "disabled";
export type ChannelSort = "name-asc" | "name-desc" | "models-desc";
