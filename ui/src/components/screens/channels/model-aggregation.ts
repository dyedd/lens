"use client";

import { useMemo } from "react";
import type { ProtocolKind } from "@/lib/api";
import {
  type FormProtocolConfig,
  genericModelKey,
  type Locale,
  protocolConfigDisplayName,
} from "./shared";

export type AggregatedModel = {
  credentialId: string;
  modelName: string;
  protocols: ProtocolKind[];
  sources: string[];
};

export function useAggregatedModels(
  protocolConfigs: FormProtocolConfig[],
  locale: Locale,
): AggregatedModel[] {
  return useMemo(() => {
    const aggregate: Record<
      string,
      { protocols: Set<ProtocolKind>; sources: Set<string> }
    > = {};
    protocolConfigs.forEach((protocolConfig, index) => {
      if (!protocolConfig.enabled) return;
      const protocolConfigName = protocolConfigDisplayName(
        protocolConfig,
        index,
        locale,
      );
      protocolConfig.models.forEach((model) => {
        const key = genericModelKey(model);
        if (!aggregate[key]) {
          aggregate[key] = { protocols: new Set(), sources: new Set() };
        }
        const modelProtocols = Array.from(new Set(model.protocols));
        modelProtocols.forEach((p) => aggregate[key].protocols.add(p));
        aggregate[key].sources.add(protocolConfigName);
      });
    });
    return Object.entries(aggregate).map(([key, { protocols, sources }]) => {
      const separatorIndex = key.indexOf(":");
      return {
        credentialId: key.slice(0, separatorIndex),
        modelName: key.slice(separatorIndex + 1),
        protocols: Array.from(protocols),
        sources: Array.from(sources),
      };
    });
  }, [protocolConfigs, locale]);
}
