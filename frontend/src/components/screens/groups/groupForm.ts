import type { ModelGroup, ModelGroupCandidateItem } from "@/lib/api/groups";
import {
  headersToRules,
  parseHeaderRows,
} from "../settings/upstreamHeaderConfig";
import type { FormItem, FormState } from "./groupTypes";

function parseRuleValue(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

/** Convert candidate payload items into editable model group members. */
export function candidatePayloadToFormItems(
  candidate: ModelGroupCandidateItem,
): FormItem[] {
  return candidate.items.map((payloadItem) => ({
    channel_id: payloadItem.channel_id,
    site_id: candidate.site_id,
    protocol_config_id: payloadItem.protocol_config_id,
    channel_name: candidate.channel_name,
    protocol: payloadItem.protocol,
    credential_id: payloadItem.credential_id,
    credential_name: candidate.credential_name,
    credential_number: candidate.credential_number,
    rate_multiplier: candidate.rate_multiplier,
    rate_source: candidate.rate_source,
    model_name: payloadItem.model_name,
    enabled: true,
    state: null,
    reasons: [],
  }));
}

/** Convert a persisted model group into editor form state. */
export function modelGroupToForm(group: ModelGroup): FormState {
  return {
    name: group.name,
    strategy: group.strategy,
    route_group_id: group.route_group_id ?? "",
    sync_filter_mode: group.sync_filter_mode,
    sync_filter_query: group.sync_filter_query,
    param_override: group.param_override.map((rule) => ({
      path: rule.path,
      action: rule.action,
      value: rule.value === undefined ? "" : JSON.stringify(rule.value),
    })),
    headers: group.headers.map((rule) => ({
      key: rule.name,
      value: rule.value,
      action: rule.action,
    })),
    input_price_per_million: String(group.input_price_per_million),
    output_price_per_million: String(group.output_price_per_million),
    cache_read_price_per_million: String(group.cache_read_price_per_million),
    cache_write_price_per_million: String(group.cache_write_price_per_million),
    image_price_per_image: String(group.image_price_per_image),
    pricing_mode: group.pricing_mode,
    items: group.items
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((item) => ({
        channel_id: item.channel_id,
        site_id: item.site_id,
        protocol_config_id: item.protocol_config_id,
        channel_name: item.channel_name,
        protocol: item.protocol,
        credential_id: item.credential_id,
        credential_name: item.credential_name,
        credential_number: item.credential_number,
        rate_multiplier: item.rate_multiplier,
        rate_source: item.rate_source,
        model_name: item.model_name,
        enabled: item.enabled,
        state: item.state,
        reasons: item.reasons,
      })),
  };
}

/** Convert editor form state into a model-group API payload. */
export function formToModelGroupPayload(form: FormState) {
  return {
    name: form.name.trim(),
    strategy: form.strategy,
    route_group_id: form.route_group_id.trim(),
    sync_filter_mode:
      form.route_group_id.trim() || !form.sync_filter_query.trim()
        ? ""
        : form.sync_filter_mode,
    sync_filter_query: form.route_group_id.trim()
      ? ""
      : form.sync_filter_query.trim(),
    param_override: form.param_override
      .filter((rule) => rule.path.trim())
      .map((rule) => ({
        path: rule.path.trim(),
        action: rule.action,
        ...(rule.action === "set" ? { value: parseRuleValue(rule.value) } : {}),
      })),
    headers: headersToRules(form.headers),
    items: form.items.map((item) => ({
      channel_id: item.channel_id,
      credential_id: item.credential_id,
      model_name: item.model_name,
      enabled: item.enabled,
    })),
  };
}
