"use client";

import { useMemo } from "react";
import type { ProtocolKind } from "@/lib/api";
import {
  baseUrlLabel,
  credentialLabel,
  type FormBaseUrl,
  type FormCredential,
  type FormProtocolConfig,
  type Locale,
  protocolConfigDisplayName,
  protocolConfigModelKey,
  protocolConfigSyncStatusLabel,
} from "./channelShared";

export type AggregatedModel = {
  key: string;
  modelName: string;
  protocols: ProtocolKind[];
  sources: string[];
};

/** Aggregates equivalent channel models and their protocol sources. */
export function useAggregatedModels(
  protocolConfigs: FormProtocolConfig[],
  baseUrls: FormBaseUrl[],
  credentials: FormCredential[],
  locale: Locale,
): AggregatedModel[] {
  return useMemo(() => {
    const aggregate: Record<
      string,
      {
        modelName: string;
        protocols: Set<ProtocolKind>;
        sources: Set<string>;
      }
    > = {};
    const credentialNameById = new Map(
      credentials.map(
        (credential, index) =>
          [credential.id, credentialLabel(credential, index, locale)] as const,
      ),
    );
    protocolConfigs.forEach((protocolConfig, index) => {
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
      protocolConfig.models.forEach((model) => {
        const credentialName =
          credentialNameById.get(model.credential_id) ||
          (locale === "zh-CN" ? "未知密钥" : "Unknown key");
        const sourceLabel = `${sourceName} · ${credentialName} · ${protocolConfigSyncStatusLabel(
          protocolConfig,
          locale,
        )}`;
        const key = protocolConfigModelKey(index, protocolConfig, model);
        if (!aggregate[key]) {
          aggregate[key] = {
            modelName: model.model_name,
            protocols: new Set(),
            sources: new Set(),
          };
        }
        const modelProtocols = Array.from(new Set(model.protocols));
        modelProtocols.forEach((p) => aggregate[key].protocols.add(p));
        aggregate[key].sources.add(sourceLabel);
      });
    });
    return Object.entries(aggregate).map(
      ([key, { modelName, protocols, sources }]) => ({
        key,
        modelName,
        protocols: Array.from(protocols),
        sources: Array.from(sources),
      }),
    );
  }, [baseUrls, credentials, protocolConfigs, locale]);
}
