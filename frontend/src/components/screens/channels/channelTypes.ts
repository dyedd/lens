import type { BatchModelTestSource } from "@/components/model-test/batchModelTestSession";
import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  ChannelProxyMode,
  Site,
  SiteBaseUrlKind,
  SiteCredential,
  SiteModelInput,
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
  kind: SiteBaseUrlKind;
  shareKeys: boolean;
  newApiKeysLines: string;
};
export type { Locale };

export type FormModel = Omit<SiteModelInput, "id" | "protocol"> & {
  protocols: ProtocolKind[];
  modelIdsByProtocol: Partial<Record<ProtocolKind, string>>;
};

export type FormProtocolConfig = {
  id: string;
  base_url_id: string;
  credential_ids: string[];
  protocols: ProtocolKind[];
  models: FormModel[];
};

export type FormState = {
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
  protocol: ProtocolKind;
  context_window: number | null;
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

export type AggregatedModelMember = {
  /** Per-credential key matching protocolConfigModelKey semantics. */
  key: string;
  credentialId: string;
  credentialName: string;
  /** Key label plus masked value. */
  credentialTitle: string;
  baseUrl: string;
};

export type AggregatedModel = {
  /** 同一渠道内同名模型共用的展示键。 */
  key: string;
  modelName: string;
  baseUrls: string[];
  /** 渠道各出口绑定的 Key 去重计数。 */
  credentialCount: number;
  protocols: ProtocolKind[];
  enabled: boolean;
  /** Admin override shared by every key's copy of this model. */
  contextWindow: number | null;
  /** Upstream-reported value used without an override. */
  /** Per-credential rows for expanding the collapsed overview row. */
  members: AggregatedModelMember[];
  /** Per-credential key used to open the single-model test dialog. */
  testKey: string | null;
};

export type ModelStatusFilter = "all" | "enabled" | "disabled";
