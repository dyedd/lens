"use client";

import { useMemo } from "react";
import type { ProtocolKind } from "@/lib/api";
import {
  baseUrlLabel,
  type FormBaseUrl,
  type FormProtocolConfig,
  type Locale,
  protocolConfigDisplayName,
  protocolConfigModelKey,
} from "./shared";

export type AggregatedModel = {
  key: string;
  modelName: string;
  protocols: ProtocolKind[];
  sources: string[];
};

export function useAggregatedModels(
  protocolConfigs: FormProtocolConfig[],
  baseUrls: FormBaseUrl[],
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
        aggregate[key].sources.add(sourceName);
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
  }, [baseUrls, protocolConfigs, locale]);
}
