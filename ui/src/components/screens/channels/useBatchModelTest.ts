"use client";

import type { ProtocolKind, SiteModelTestPayload } from "@/lib/api";
import { useBatchModelTestSession } from "../batchModelTestSession";
import type {
  Locale,
  ModelTestTarget,
  TestableModelOption,
} from "./channelShared";

type PayloadBuilder = (
  target: ModelTestTarget,
  protocol: ProtocolKind | null,
  prompt: string,
) => SiteModelTestPayload | null;

/** Adapts editable channel models to the shared batch-test session. */
export function useBatchModelTest({
  locale,
  prompts,
  optionByKey,
  buildPayload,
}: {
  locale: Locale;
  prompts: string[];
  optionByKey: Map<string, TestableModelOption>;
  buildPayload: PayloadBuilder;
}) {
  return useBatchModelTestSession({
    locale,
    prompts,
    optionByKey,
    prepareRequest: (target, protocol, prompt) => {
      const payload = buildPayload(target, protocol, prompt);
      if (!payload) return null;
      return {
        path: "/admin/site-model-tests",
        payload,
        modelName: payload.model_name,
        credentialName: payload.credential.name,
        protocol: payload.protocol,
      };
    },
  });
}
