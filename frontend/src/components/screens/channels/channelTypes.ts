import type { BatchModelTestSource } from "@/components/model-test/batchModelTestSession";
import type { ProtocolKind } from "@/lib/api/protocols";
import type {
  ChannelProxyMode,
  Site,
  SiteCredential,
  SiteModelInput,
} from "@/lib/api/sites";
import type { ContextWindowSource } from "@/lib/contextWindow";
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

export type FormState = {
  name: string;
  tags: string[];
  newApiKeysLines: string;
  base_urls: FormBaseUrl[];
  credentials: FormCredential[];
  protocolConfigs: FormProtocolConfig[];
  proxy_mode: ChannelProxyMode;
  channel_proxy: string;
  /** Library regex rules that auto-onboard matching upstream models. */
  model_sync_include_rule_ids: string[];
  /** Library regex rules that keep matching upstream models out. */
  model_sync_exclude_rule_ids: string[];
  /** Vendor prefixes aliasing "openai/gpt-5" to "gpt-5"; last alias wins. */
  model_name_prefixes: string[];
  headersJson: string;
  paramsJson: string;
};

export type PickerModelItem = {
  protocol_config_id: string;
  credential_id: string;
  model_name: string;
  /** Context window the upstream model list reports. */
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
};

export type AggregatedModel = {
  /** Group key shared by every same-name model inside one protocol config. */
  key: string;
  modelName: string;
  /** Base URL of the protocol config that owns this row. */
  baseUrl: string;
  /** Number of keys bound to the owning protocol config. */
  credentialCount: number;
  protocols: ProtocolKind[];
  enabled: boolean;
  upstreamMissing: boolean;
  /** Admin override shared by every key's copy of this model. */
  contextWindow: number | null;
  /** Upstream-reported or name-detected value used without an override. */
  autoContextWindow: number | null;
  autoContextWindowSource: Exclude<ContextWindowSource, "manual"> | null;
  /** Per-credential rows for expanding the collapsed overview row. */
  members: AggregatedModelMember[];
  /** Per-credential key used to open the single-model test dialog. */
  testKey: string | null;
};

export type ModelStatusFilter = "all" | "enabled" | "disabled" | "missing";
