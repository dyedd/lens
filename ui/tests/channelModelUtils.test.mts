import assert from "node:assert/strict";
import test from "node:test";
import type { ProtocolKind } from "../src/lib/api";
import type {
  FormModel,
  FormSyncTarget,
  PickerModelItem,
} from "../src/components/screens/channels/channelTypes";

const moduleUrl = new URL(
  "../src/components/screens/channels/channelModelUtils.ts",
  import.meta.url,
).href;
const {
  coalesceFormModels,
  replaceSyncedModels,
}: {
  coalesceFormModels: (models: FormModel[]) => FormModel[];
  replaceSyncedModels: (
    models: FormModel[],
    syncTargets: FormSyncTarget[],
    fetched: PickerModelItem[],
    protocols: ProtocolKind[],
  ) => {
    models: FormModel[];
    syncTargets: FormSyncTarget[];
    removedCount: number;
  };
} = await import(moduleUrl);

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

test("replaces exact sync targets while leaving manual conflicts alone", () => {
  const { models, syncTargets, removedCount } = replaceSyncedModels(
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
      {
        credential_id: "credential-1",
        model_name: "dropped-upstream",
        protocol: "openai_chat",
      },
      {
        credential_id: "credential-2",
        model_name: "other-credential",
        protocol: "openai_chat",
      },
    ],
    [
      { credential_id: "credential-1", model_name: "gpt-4.1" },
      { credential_id: "credential-1", model_name: "gpt-5" },
    ],
    ["openai_chat"],
  );
  const byName = new Map(models.map((model) => [model.model_name, model]));

  // A same-name manual model remains manual and cannot gain a sync target.
  assert.deepEqual(byName.get("gpt-4.1"), {
    credential_id: "credential-1",
    model_name: "gpt-4.1",
    enabled: true,
    source: "manual",
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
  assert.deepEqual(syncTargets, [
    {
      credential_id: "credential-2",
      model_name: "other-credential",
      protocol: "openai_chat",
    },
    {
      credential_id: "credential-1",
      model_name: "gpt-5",
      protocol: "openai_chat",
    },
  ]);
  assert.equal(models.length, 4);
  assert.equal(removedCount, 1);
});

test("does not create a target for a matching manual model", () => {
  // Both rows describe the same model under different sources, so coalescing
  // collapses them; that must not read as an upstream removal.
  const { models, syncTargets, removedCount } = replaceSyncedModels(
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
    [
      {
        credential_id: "credential-1",
        model_name: "gpt-4.1",
        protocol: "openai_chat",
      },
    ],
    [{ credential_id: "credential-1", model_name: "gpt-4.1" }],
    ["openai_chat"],
  );

  assert.equal(models.length, 1);
  assert.deepEqual(syncTargets, []);
  assert.equal(removedCount, 0);
});
