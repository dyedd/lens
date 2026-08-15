"use client";

import { useMemo } from "react";
import type { ProtocolKind, SiteModelInput } from "@/lib/api";
import {
  baseUrlLabel,
  credentialLabel,
  type FormBaseUrl,
  type FormCredential,
  type FormProtocolConfig,
  type Locale,
  protocolConfigDisplayName,
  protocolConfigModelKey,
  syncTargetKey,
} from "./channelShared";

export type AggregatedModel = {
  key: string;
  modelName: string;
  protocols: ProtocolKind[];
  sourceLabel: string;
  source: SiteModelInput["source"];
  isTargetOnly: boolean;
};

/** Builds the model rows shown in the channel overview. */
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
      const rows = new Map<string, AggregatedModel>(
        protocolConfig.models.map((model) => {
          const key = protocolConfigModelKey(protocolConfig, model);
          return [
            key,
            {
              key,
              modelName: model.model_name,
              protocols: model.protocols,
              sourceLabel: `${sourceName} · ${credentialName(model.credential_id)}`,
              source: model.source,
              isTargetOnly: false,
            },
          ] as const;
        }),
      );

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

        const key = protocolConfigModelKey(protocolConfig, {
          ...target,
          source: "synced",
        });
        const existing = rows.get(key);
        if (existing) {
          existing.protocols = Array.from(
            new Set([...existing.protocols, target.protocol]),
          );
          continue;
        }
        rows.set(key, {
          key,
          modelName: target.model_name,
          protocols: [target.protocol],
          sourceLabel: `${sourceName} · ${credentialName(target.credential_id)}`,
          source: "synced",
          isTargetOnly: true,
        });
      }

      return Array.from(rows.values());
    });
  }, [baseUrls, credentials, protocolConfigs, locale]);
}
