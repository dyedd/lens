import { useMemo } from "react";
import type { ProtocolKind } from "@/lib/api/protocols";
import { credentialLabel, formatCredentialTitle } from "@/lib/credentialLabels";
import {
  activeBaseUrlValue,
  protocolConfigSelectedCredentialIds,
} from "./channelForm";
import {
  aggregateModelGroupKey,
  protocolConfigModelKey,
} from "./channelModels";
import type {
  AggregatedModel,
  AggregatedModelMember,
  FormState,
  Locale,
} from "./channelTypes";

type ModelGroupSeed = {
  modelName: string;
  baseUrls: Set<string>;
  protocols: Set<ProtocolKind>;
  enabled: boolean;
  contextWindow: number | null;
  members: Map<string, AggregatedModelMember>;
  testKey: string | null;
};

/** 同名模型合并显示，保留每把 Key 在各地址的记录。 */
export function useAggregatedModels(
  form: Pick<FormState, "base_urls" | "credentials" | "protocolConfigs">,
  locale: Locale,
): AggregatedModel[] {
  const { base_urls: baseUrls, credentials, protocolConfigs } = form;
  return useMemo(() => {
    const credentialById = new Map(
      credentials.map(
        (credential, index) => [credential.id, { credential, index }] as const,
      ),
    );
    const unknownKey = locale === "zh-CN" ? "未知密钥" : "Unknown key";
    const credentialNames = (credentialId: string) => {
      const entry = credentialById.get(credentialId);
      if (!entry) return { name: unknownKey, title: unknownKey };
      return {
        name: credentialLabel(entry.credential, entry.index, locale),
        title: formatCredentialTitle(entry.credential, entry.index, locale),
      };
    };
    const credentialCount = new Set(
      protocolConfigs.flatMap(protocolConfigSelectedCredentialIds),
    ).size;
    const groups = new Map<string, ModelGroupSeed>();
    for (const protocolConfig of protocolConfigs) {
      const baseUrl = activeBaseUrlValue(
        { base_urls: baseUrls },
        protocolConfig,
      ).trim();
      const groupOf = (modelName: string, contextWindow: number | null) => {
        const existing = groups.get(modelName);
        if (existing) return existing;
        const created: ModelGroupSeed = {
          modelName,
          baseUrls: new Set(),
          protocols: new Set(),
          enabled: false,
          contextWindow,
          members: new Map(),
          testKey: null,
        };
        groups.set(modelName, created);
        return created;
      };

      for (const model of protocolConfig.models) {
        const group = groupOf(model.model_name, model.context_window);
        group.baseUrls.add(baseUrl);
        for (const protocol of model.protocols) {
          group.protocols.add(protocol);
        }
        group.enabled = group.enabled || model.enabled;
        if (group.contextWindow !== model.context_window)
          group.contextWindow = null;
        const memberKey = protocolConfigModelKey(protocolConfig, model);
        if (group.members.has(memberKey)) continue;
        const names = credentialNames(model.credential_id);
        group.members.set(memberKey, {
          key: memberKey,
          credentialId: model.credential_id,
          credentialName: names.name,
          credentialTitle: names.title,
          baseUrl,
          protocols: model.protocols,
        });
        group.testKey ??= memberKey;
      }
    }
    return Array.from(groups.values()).map((group) => ({
      key: aggregateModelGroupKey(group.modelName),
      modelName: group.modelName,
      baseUrls: Array.from(group.baseUrls),
      credentialCount,
      protocols: Array.from(group.protocols),
      enabled: group.enabled,
      contextWindow: group.contextWindow,
      members: Array.from(group.members.values()),
      testKey: group.testKey,
    }));
  }, [baseUrls, credentials, protocolConfigs, locale]);
}
