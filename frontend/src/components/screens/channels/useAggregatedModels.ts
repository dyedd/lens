import { useMemo } from "react";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { SiteModelInput } from "@/lib/api/sites";
import {
  activeBaseUrlValue,
  protocolConfigSelectedCredentialIds,
} from "./channelForm";
import {
  aggregateModelGroupKey,
  credentialLabel,
  formatCredentialTitle,
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
  protocols: Set<ProtocolKind>;
  sources: Set<SiteModelInput["source"]>;
  enabled: boolean;
  upstreamMissing: boolean;
  members: Map<string, AggregatedModelMember>;
  testKey: string | null;
};

/**
 * Builds the channel overview rows, collapsing models that share a name
 * within one protocol configuration so multi-key duplicates stay one row.
 */
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
    return protocolConfigs.flatMap((protocolConfig) => {
      const baseUrl = activeBaseUrlValue(
        { base_urls: baseUrls },
        protocolConfig,
      ).trim();
      const credentialCount =
        protocolConfigSelectedCredentialIds(protocolConfig).length;
      const groups = new Map<string, ModelGroupSeed>();
      const groupOf = (modelName: string) => {
        const existing = groups.get(modelName);
        if (existing) return existing;
        const created: ModelGroupSeed = {
          modelName,
          protocols: new Set(),
          sources: new Set(),
          enabled: false,
          upstreamMissing: false,
          members: new Map(),
          testKey: null,
        };
        groups.set(modelName, created);
        return created;
      };

      for (const model of protocolConfig.models) {
        const group = groupOf(model.model_name);
        for (const protocol of model.protocols) {
          group.protocols.add(protocol);
        }
        group.sources.add(model.source);
        group.enabled = group.enabled || model.enabled;
        group.upstreamMissing = group.upstreamMissing || model.upstream_missing;
        const memberKey = protocolConfigModelKey(protocolConfig, model);
        if (group.members.has(memberKey)) continue;
        const names = credentialNames(model.credential_id);
        group.members.set(memberKey, {
          key: memberKey,
          credentialId: model.credential_id,
          credentialName: names.name,
          credentialTitle: names.title,
          source: model.source,
        });
        group.testKey ??= memberKey;
      }

      return Array.from(groups.values()).map((group) => ({
        key: aggregateModelGroupKey(protocolConfig, group.modelName),
        modelName: group.modelName,
        baseUrl,
        credentialCount,
        protocols: Array.from(group.protocols),
        source: group.sources.has("manual") ? "manual" : "synced",
        enabled: group.enabled,
        upstreamMissing: group.upstreamMissing,
        members: Array.from(group.members.values()),
        testKey: group.testKey,
      }));
    });
  }, [baseUrls, credentials, protocolConfigs, locale]);
}
