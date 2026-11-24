import { describe, expect, it } from "vitest";
import type { Site } from "@/lib/api/sites";
import { applyApiKeyDrafts, emptyForm } from "./channelForm";
import { toForm, toPayload } from "./channelFormConversion";

describe("channel form conversion", () => {
  it("deduplicates new API keys and includes them in the create payload", () => {
    const form = emptyForm();
    form.name = "Primary";
    form.base_urls[0].url = "https://api.example.com/v1";
    form.newApiKeysLines = "sk-one\nsk-one\nsk-two";

    const payload = toPayload(applyApiKeyDrafts(form));

    expect(payload.credentials.map((credential) => credential.api_key)).toEqual(
      ["sk-one", "sk-two"],
    );
    expect(
      payload.credentials.every(
        (credential) => !credential.id?.startsWith("pending-"),
      ),
    ).toBe(true);
  });

  it("preserves a saved credential when converting an existing site for editing", () => {
    const site = {
      id: "site-1",
      name: "Primary",
      enabled: true,
      supports_model_listing: true,
      tags: [],
      proxy_mode: "inherit",
      channel_proxy: "",
      headers: [],
      param_override: [],
      base_urls: [
        {
          id: "base-url-1",
          url: "https://api.example.com/v1",
          sort_order: 0,
          kind: "default",
        },
      ],
      credentials: [
        {
          id: "credential-1",
          name: "Primary key",
          api_key: "sk-existing",
          sort_order: 0,
          base_url_ids: null,
          rate_source: "none",
          rate_protocol_config_id: "",
          rate_group: "",
          rate_multiplier: null,
          rate_observed_at: null,
          rate_last_synced_at: null,
          rate_last_error: "",
        },
      ],
      protocols: [],
    } satisfies Site;

    const payload = toPayload(toForm(site));

    expect(payload.credentials).toMatchObject([
      { id: "credential-1", name: "Primary key", api_key: "sk-existing" },
    ]);
  });
});
