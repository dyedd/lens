"use client";

import { useMemo, useState } from "react";
import type { ModelGroupItem, ModelGroupModelTestPayload } from "@/lib/api";
import {
  type BatchModelTestSource,
  useBatchModelTestSession,
} from "../batchModelTestSession";
import { useModelTestPrompts } from "../modelTestSession";
import {
  credentialDisplayLabel,
  itemKey,
  type GroupRow,
} from "./modelGroupUtils";

type TestTarget = {
  groupId: string;
  item: ModelGroupItem;
  credentialName: string;
};

/** Owns batch member testing launched from a persisted model-group card. */
export function useGroupModelTest(locale: "zh-CN" | "en-US") {
  const [targetGroup, setTargetGroup] = useState<GroupRow | null>(null);
  const prompts = useModelTestPrompts();
  const optionByKey = useMemo(() => {
    const options = new Map<string, BatchModelTestSource<TestTarget>>();
    if (!targetGroup) return options;
    for (const item of targetGroup.items) {
      if (!item.enabled || item.state !== "ready" || !item.protocol) continue;
      const credentialName = [
        item.channel_name || item.channel_id,
        credentialDisplayLabel(item, locale),
      ]
        .filter(Boolean)
        .join(" · ");
      const key = itemKey(item);
      options.set(key, {
        key,
        target: { groupId: targetGroup.id, item, credentialName },
        modelName: item.model_name,
        credentialName,
        protocols: [item.protocol],
      });
    }
    return options;
  }, [locale, targetGroup]);
  const modelTest = useBatchModelTestSession({
    locale,
    prompts,
    optionByKey,
    prepareRequest: (target, protocol, prompt) => {
      const { item } = target;
      if (item.protocol !== protocol) return null;
      const payload: ModelGroupModelTestPayload = {
        channel_id: item.channel_id,
        credential_id: item.credential_id,
        model_name: item.model_name,
        prompt,
      };
      return {
        path: `/admin/model-groups/${target.groupId}/model-tests`,
        payload,
        modelName: item.model_name,
        credentialName: target.credentialName,
        protocol,
      };
    },
  });

  function openModelTest(group: GroupRow) {
    setTargetGroup(group);
    modelTest.openBatchModelTestDialog();
  }

  function changeModelTestOpen(open: boolean) {
    modelTest.changeBatchModelTestOpen(open);
    if (!open) setTargetGroup(null);
  }

  return {
    ...modelTest,
    changeBatchModelTestOpen: changeModelTestOpen,
    modelTestPrompts: prompts,
    openModelTest,
    testingModel: modelTest.isBatchModelTestRunning,
  };
}
