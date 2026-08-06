import assert from "node:assert/strict";
import test from "node:test";

const moduleUrl = new URL(
  "../src/components/screens/channels/channelModelUtils.ts",
  import.meta.url,
).href;
const { coalesceFormModels, mergeSyncedModels } = await import(moduleUrl);

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

test("replaces the synced set with the fetched models", () => {
  const { models, removedCount } = mergeSyncedModels(
    [
      {
        credential_id: "credential-1",
        model_name: "gpt-4.1",
        enabled: true,
        source: "manual",
        protocols: ["openai_responses"],
        protocolIds: { openai_responses: "responses-row" },
      },
      {
        credential_id: "credential-1",
        model_name: "pinned-model",
        enabled: true,
        source: "manual",
        protocols: ["openai_chat"],
        protocolIds: { openai_chat: "pinned-row" },
      },
      {
        credential_id: "credential-1",
        model_name: "dropped-upstream",
        enabled: true,
        source: "synced",
        protocols: ["openai_chat"],
        protocolIds: { openai_chat: "dropped-row" },
      },
      {
        credential_id: "credential-2",
        model_name: "other-credential",
        enabled: true,
        source: "synced",
        protocols: ["openai_chat"],
        protocolIds: { openai_chat: "other-row" },
      },
    ],
    [
      { credential_id: "credential-1", model_name: "gpt-4.1" },
      { credential_id: "credential-1", model_name: "gpt-5" },
    ],
    ["openai_chat"],
  );
  const byName = new Map(models.map((model) => [model.model_name, model]));

  // Fetched row flips to synced but keeps its protocols and persisted ids.
  assert.deepEqual(byName.get("gpt-4.1"), {
    credential_id: "credential-1",
    model_name: "gpt-4.1",
    enabled: true,
    source: "synced",
    protocols: ["openai_responses"],
    protocolIds: { openai_responses: "responses-row" },
  });
  assert.deepEqual(byName.get("gpt-5"), {
    credential_id: "credential-1",
    model_name: "gpt-5",
    enabled: true,
    source: "synced",
    protocols: ["openai_chat"],
    protocolIds: {},
  });
  // Manual models survive even when the upstream no longer lists them.
  assert.equal(byName.get("pinned-model")?.source, "manual");
  // Synced models the upstream dropped are pruned.
  assert.equal(byName.has("dropped-upstream"), false);
  // Credentials missing from the response are left alone.
  assert.equal(byName.get("other-credential")?.source, "synced");
  assert.equal(models.length, 4);
  assert.equal(removedCount, 1);
});

test("counts only pruned models, not rows merged as equivalent", () => {
  // Both rows describe the same model under different sources, so coalescing
  // collapses them; that must not read as an upstream removal.
  const { models, removedCount } = mergeSyncedModels(
    [
      {
        credential_id: "credential-1",
        model_name: "gpt-4.1",
        enabled: true,
        source: "manual",
        protocols: ["openai_chat"],
        protocolIds: { openai_chat: "chat-row" },
      },
      {
        credential_id: "credential-1",
        model_name: "gpt-4.1",
        enabled: true,
        source: "synced",
        protocols: ["openai_chat"],
        protocolIds: { openai_chat: "chat-row" },
      },
    ],
    [{ credential_id: "credential-1", model_name: "gpt-4.1" }],
    ["openai_chat"],
  );

  assert.equal(models.length, 1);
  assert.equal(removedCount, 0);
});
