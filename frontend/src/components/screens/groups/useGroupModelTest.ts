import { useState } from "react";
import {
  type BatchModelTestSource,
  useBatchModelTestSession,
} from "@/components/model-test/batchModelTestSession";
import { useModelTestPrompts } from "@/components/model-test/modelTestSession";
import type {
  ModelGroupItem,
  ModelGroupModelTestPayload,
} from "@/lib/api/groups";
import { PROTOCOL_LIST } from "@/lib/protocols";
import type { GroupRow } from "./groupTypes";
import {
  credentialDisplayLabel,
  modelGroupItemKey,
} from "./modelGroupFormatting";

type TestTarget = {
  groupId: string;
  item: ModelGroupItem;
  credentialName: string;
};

/** Owns batch member testing launched from a persisted model-group card. */
export function useGroupModelTest(locale: "zh-CN" | "en-US") {
  const [targetGroup, setTargetGroup] = useState<GroupRow | null>(null);
  const prompts = useModelTestPrompts();
  const modelTest = useBatchModelTestSession<TestTarget>({
    locale,
    prompts,
    prepareRequest: (target, protocol, prompt) => {
      const { item } = target;
      if (item.protocol !== "auto" && item.protocol !== protocol) return null;
      const payload: ModelGroupModelTestPayload = {
        channel_id: item.channel_id,
        credential_id: item.credential_id,
        model_name: item.model_name,
        prompt,
        protocol,
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
    const sources: BatchModelTestSource<TestTarget>[] = [];
    for (const item of group.items) {
      if (!item.enabled || item.state !== "ready" || !item.protocol) continue;
      const credentialName = [
        item.channel_name || item.channel_id,
        credentialDisplayLabel(item, locale),
      ]
        .filter(Boolean)
        .join(" · ");
      sources.push({
        key: modelGroupItemKey(item),
        target: { groupId: group.id, item, credentialName },
        modelName: item.model_name,
        credentialName,
        protocols: item.protocol === "auto" ? PROTOCOL_LIST : [item.protocol],
      });
    }
    setTargetGroup(group);
    modelTest.openBatchModelTestDialog(sources);
  }

  function changeModelTestOpen(open: boolean) {
    modelTest.changeBatchModelTestOpen(open);
    if (!open) setTargetGroup(null);
  }

  return {
    ...modelTest,
    changeBatchModelTestOpen: changeModelTestOpen,
    targetName: targetGroup?.name || "",
    openModelTest,
    testingModel: modelTest.isBatchModelTestRunning,
  };
}
