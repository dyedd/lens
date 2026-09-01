import { useMemo } from "react";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { SiteModelInput } from "@/lib/api/sites";
import {
  baseUrlLabel,
  credentialLabel,
  protocolConfigDisplayName,
} from "./channelLabels";
import {
  aggregateModelGroupKey,
  protocolConfigModelKey,
  syncTargetKey,
} from "./channelModelUtils";
import type {
  FormBaseUrl,
  FormCredential,
  FormProtocolConfig,
  Locale,
} from "./channelTypes";

export type AggregatedModelMember = {
  /** Per-credential key matching protocolConfigModelKey semantics. */
  key: string;
  credentialName: string;
  source: SiteModelInput["source"];
  isTargetOnly: boolean;
};

export type AggregatedModel = {
  /** Group key shared by every same-name model inside one protocol config. */
  key: string;
  modelName: string;
  protocols: ProtocolKind[];
  sourceLabel: string;
  source: SiteModelInput["source"];
  /** Per-credential rows for expanding the collapsed overview row. */
  members: AggregatedModelMember[];
  /** Per-credential key used to open the single-model test dialog. */
  testKey: string | null;
};

type ModelGroupSeed = {
  modelName: string;
  protocols: Set<ProtocolKind>;
  sources: Set<SiteModelInput["source"]>;
  members: AggregatedModelMember[];
  testKey: string | null;
};

/**
 * Builds the channel overview rows, collapsing models that share a name
 * within one protocol configuration so multi-key duplicates stay one row.
 */
export function useAggregatedModels(
  protocolConfigs: FormProtocolConfig[],
  baseUrls: FormBaseUrl[],
  credentials: FormCredential[],
  locale: Locale,
): AggregatedModel[] {
  return useMemo(() => {
    const credentialNameById = new Map(
      credentials.map(
        (credential, index) =>
          [credential.id, credentialLabel(credential, index, locale)] as const,
      ),
    );
    const credentialName = (credentialId: string) =>
      credentialNameById.get(credentialId) ||
      (locale === "zh-CN" ? "未知密钥" : "Unknown key");
    return protocolConfigs.flatMap((protocolConfig, index) => {
      const baseUrlIndex = baseUrls.findIndex(
        (item) => item.id === protocolConfig.base_url_id,
      );
      const baseUrl = baseUrlIndex >= 0 ? baseUrls[baseUrlIndex] : undefined;
      const protocolConfigName = protocolConfigDisplayName(
        protocolConfig,
        index,
        locale,
      );
      const sourceName = baseUrl
        ? `${protocolConfigName} · ${baseUrlLabel(baseUrl, baseUrlIndex, locale)}`
        : protocolConfigName;
      const groups = new Map<string, ModelGroupSeed>();
      const groupOf = (modelName: string) => {
        const existing = groups.get(modelName);
        if (existing) return existing;
        const created: ModelGroupSeed = {
          modelName,
          protocols: new Set(),
          sources: new Set(),
          members: [],
          testKey: null,
        };
        groups.set(modelName, created);
        return created;
      };
      const addMember = (
        group: ModelGroupSeed,
        memberKey: string,
        credentialId: string,
        source: SiteModelInput["source"],
        isTargetOnly: boolean,
      ) => {
        const existing = group.members.find(
          (member) => member.key === memberKey,
        );
        if (existing) {
          existing.isTargetOnly = existing.isTargetOnly && isTargetOnly;
          return;
        }
        group.members.push({
          key: memberKey,
          credentialName: credentialName(credentialId),
          source,
          isTargetOnly,
        });
        if (!group.testKey && !isTargetOnly) group.testKey = memberKey;
      };

      for (const model of protocolConfig.models) {
        const group = groupOf(model.model_name);
        for (const protocol of model.protocols) {
          group.protocols.add(protocol);
        }
        group.sources.add(model.source);
        addMember(
          group,
          protocolConfigModelKey(protocolConfig, model),
          model.credential_id,
          model.source,
          false,
        );
      }

      const syncedProtocolKeys = new Set(
        protocolConfig.models
          .filter((model) => model.source === "synced")
          .flatMap((model) =>
            model.protocols.map((protocol) =>
              syncTargetKey({
                credential_id: model.credential_id,
                model_name: model.model_name,
                protocol,
              }),
            ),
          ),
      );
      for (const target of protocolConfig.sync_targets) {
        if (syncedProtocolKeys.has(syncTargetKey(target))) continue;
        const group = groupOf(target.model_name);
        group.protocols.add(target.protocol);
        group.sources.add("synced");
        addMember(
          group,
          protocolConfigModelKey(protocolConfig, {
            ...target,
            source: "synced",
          }),
          target.credential_id,
          "synced",
          true,
        );
      }

      return Array.from(groups.values()).map((group) => ({
        key: aggregateModelGroupKey(protocolConfig, group.modelName),
        modelName: group.modelName,
        protocols: Array.from(group.protocols),
        sourceLabel: `${sourceName} · ${group.members
          .map((member) => member.credentialName)
          .join(locale === "zh-CN" ? "、" : ", ")}`,
        source: group.sources.has("manual") ? "manual" : "synced",
        members: group.members,
        testKey: group.testKey,
      }));
    });
  }, [baseUrls, credentials, protocolConfigs, locale]);
}
