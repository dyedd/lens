import assert from "node:assert/strict";
import test from "node:test";

const moduleUrl = new URL(
  "../src/components/screens/channels/channelModelUtils.ts",
  import.meta.url,
).href;
const { coalesceFormModels } = await import(moduleUrl);

test("coalesces models that become equivalent after a source change", () => {
  const models = coalesceFormModels([
    {
      credential_id: "credential-1",
      model_name: "gpt-4.1",
      enabled: false,
      source: "manual",
      protocols: ["openai_chat"],
      protocolIds: { openai_chat: "chat-row" },
    },
    {
      credential_id: "credential-1",
      model_name: "gpt-4.1",
      enabled: true,
      source: "manual",
      protocols: ["openai_responses"],
      protocolIds: { openai_responses: "responses-row" },
    },
  ]);

  assert.deepEqual(models, [
    {
      credential_id: "credential-1",
      model_name: "gpt-4.1",
      enabled: true,
      source: "manual",
      protocols: ["openai_chat", "openai_responses"],
      protocolIds: {
        openai_chat: "chat-row",
        openai_responses: "responses-row",
      },
    },
  ]);
});

test("keeps manual and synchronized models separate", () => {
  const baseModel = {
    credential_id: "credential-1",
    model_name: "gpt-4.1",
    enabled: true,
    protocols: ["openai_chat" as const],
    protocolIds: { openai_chat: "chat-row" },
  };

  assert.equal(
    coalesceFormModels([
      { ...baseModel, source: "manual" },
      { ...baseModel, source: "synced" },
    ]).length,
    2,
  );
});
