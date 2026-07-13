import type { Locale } from "@/lib/I18nContext";
import { defaultProtocolConfigName } from "./channelLabels";
import type { FormProtocolConfig, FormState } from "./channelTypes";

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

/** Creates a new protocol configuration with editor defaults. */
export const emptyProtocolConfig = (
  baseUrlId = "",
  name = "",
  credentialId = "",
): FormProtocolConfig => ({
  id: null,
  name,
  enabled: true,
  headers: [{ key: "", value: "" }],
  proxy_mode: "inherit",
  channel_proxy: "",
  param_override: "",
  match_regex: "",
  manual_model_name: "",
  manual_protocols: [],
  base_url_id: baseUrlId,
  credential_id: credentialId,
  credential_ids: credentialId ? [credentialId] : [],
  auto_sync_enabled: false,
  models: [],
  expanded: true,
});

/** Creates a channel editor form with one URL, credential, and combination. */
export const emptyForm = (locale: Locale = "zh-CN"): FormState => {
  const baseUrlId = createLocalId("baseurl");
  const credentialId = createLocalId("credential");
  return {
    name: "",
    base_urls: [
      {
        id: baseUrlId,
        url: "",
        name: "",
        enabled: true,
        supported_protocols: [],
      },
    ],
    credentials: [{ id: credentialId, name: "", api_key: "", enabled: true }],
    protocolConfigs: [
      emptyProtocolConfig(
        baseUrlId,
        defaultProtocolConfigName(0, locale),
        credentialId,
      ),
    ],
  };
};
