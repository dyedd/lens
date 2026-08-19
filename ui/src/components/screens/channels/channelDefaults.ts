import type { Locale } from "@/lib/I18nContext";
import { defaultProtocolConfigName } from "./channelLabels";
import type {
  FormCredential,
  FormProtocolConfig,
  FormState,
} from "./channelTypes";

/** Creates a client-side identifier for unsaved channel entities. */
export function createLocalId(prefix: string) {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function emptyCredential(): FormCredential {
  return {
    id: createLocalId("credential"),
    name: "",
    api_key: "",
    enabled: true,
    rate_source: "none",
    rate_protocol_config_id: "",
    rate_group: "",
    rate_multiplier: null,
    rate_observed_at: null,
    rate_last_synced_at: null,
    rate_last_error: "",
  };
}

/** Creates a new protocol configuration with editor defaults. */
export const emptyProtocolConfig = (
  baseUrlId = "",
  name = "",
  credentialId = "",
): FormProtocolConfig => ({
  id: createLocalId("protocol"),
  name,
  enabled: true,
  headers: [{ key: "", value: "" }],
  proxy_mode: "inherit",
  channel_proxy: "",
  param_override: "",
  model_filter: "",
  sync_new_models: false,
  manual_model_name: "",
  manual_protocols: [],
  base_url_id: baseUrlId,
  credential_ids: credentialId ? [credentialId] : [],
  sync_targets: [],
  models: [],
  expanded: true,
});

/** Creates a channel editor form with one URL, credential, and combination. */
export const emptyForm = (locale: Locale = "zh-CN"): FormState => {
  const baseUrlId = createLocalId("baseurl");
  const credential = emptyCredential();
  return {
    name: "",
    tags: [],
    base_urls: [
      {
        id: baseUrlId,
        url: "",
        name: "",
        enabled: true,
        supported_protocols: [],
      },
    ],
    credentials: [credential],
    protocolConfigs: [
      emptyProtocolConfig(
        baseUrlId,
        defaultProtocolConfigName(0, locale),
        credential.id,
      ),
    ],
  };
};
