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
} from "./channelShared";

export type AggregatedModel = {
  key: string;
  modelName: string;
  protocols: ProtocolKind[];
  sourceLabel: string;
  source: SiteModelInput["source"];
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
      return protocolConfig.models.map((model) => {
        const credentialName =
          credentialNameById.get(model.credential_id) ||
          (locale === "zh-CN" ? "未知密钥" : "Unknown key");
        return {
          key: protocolConfigModelKey(protocolConfig, model),
          modelName: model.model_name,
          protocols: model.protocols,
          sourceLabel: `${sourceName} · ${credentialName}`,
          source: model.source,
        };
      });
    });
  }, [baseUrls, credentials, protocolConfigs, locale]);
}
