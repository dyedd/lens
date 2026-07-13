import type { Site } from "@/lib/api";
import type { Locale } from "@/lib/I18nContext";
import { isGeneratedCredentialName } from "@/lib/utils";
import { protocolConfigAutoSyncActive, safeText } from "./channelFormUtils";
import type { FormProtocolConfig } from "./channelTypes";

/** Builds the fallback persisted name for a credential. */
export function fallbackCredentialName(index: number) {
  return `Key ${index + 1}`;
}

/** Formats a positional credential label for the requested locale. */
export function credentialIndexLabel(index: number, locale: string) {
  return locale === "zh-CN" ? `密钥 ${index + 1}` : `Key ${index + 1}`;
}

/** Returns a credential name or its localized positional fallback. */
export function credentialLabel(
  item: { name: string },
  index: number,
  locale: string,
) {
  const name = item.name.trim();
  if (name) return name;
  return credentialIndexLabel(index, locale);
}

/** Formats a positional base URL label for the requested locale. */
export function baseUrlIndexLabel(index: number, locale: string) {
  return locale === "zh-CN" ? `地址 ${index + 1}` : `URL ${index + 1}`;
}

/** Returns a base URL name or its localized positional fallback. */
export function baseUrlLabel(
  item: { name: string },
  index: number,
  locale: string,
) {
  const name = item.name.trim();
  if (name) return name;
  return baseUrlIndexLabel(index, locale);
}

/** Builds a localized default name for a protocol configuration. */
export function defaultProtocolConfigName(index: number, locale: string) {
  return locale === "zh-CN" ? `组合 ${index + 1}` : `Combination ${index + 1}`;
}

/** Returns a protocol configuration name or its localized fallback. */
export function protocolConfigDisplayName(
  item: { name?: string | null },
  index: number,
  locale: string,
) {
  const name = safeText(item.name).trim();
  return name || defaultProtocolConfigName(index, locale);
}

/** Finds the next unused localized protocol configuration name. */
export function nextProtocolConfigName(
  protocolConfigs: Array<{ name?: string | null }>,
  locale: string,
) {
  const usedNames = new Set(
    protocolConfigs
      .map((item, index) =>
        protocolConfigDisplayName(item, index, locale).toLowerCase(),
      )
      .filter(Boolean),
  );
  for (
    let index = protocolConfigs.length;
    index < protocolConfigs.length + 1000;
    index += 1
  ) {
    const candidate = defaultProtocolConfigName(index, locale);
    if (!usedNames.has(candidate.toLowerCase())) {
      return candidate;
    }
  }
  return defaultProtocolConfigName(protocolConfigs.length, locale);
}

/** Returns a human-facing credential name with generated-name handling. */
export function credentialDisplayName(
  credential: Site["credentials"][number] | undefined,
  index: number,
  locale: Locale,
) {
  if (!credential) {
    return locale === "zh-CN" ? `密钥 ${index + 1}` : `Key ${index + 1}`;
  }
  if (!credential.name.trim() || isGeneratedCredentialName(credential.name)) {
    return locale === "zh-CN" ? `密钥 ${index + 1}` : `Key ${index + 1}`;
  }
  return credential.name.trim();
}

/** Formats the synchronization mode of a protocol configuration. */
export function protocolConfigSyncStatusLabel(
  protocolConfig: Pick<FormProtocolConfig, "auto_sync_enabled" | "match_regex">,
  locale: Locale,
) {
  if (protocolConfigAutoSyncActive(protocolConfig)) {
    return locale === "zh-CN" ? "自动同步" : "Auto sync";
  }
  return locale === "zh-CN" ? "手动维护" : "Manual";
}
