import type { ModelGroupCandidateItem } from "@/lib/api/groups";
import { protocolLabel } from "@/lib/protocols";
import type { CandidateSearchMode, FormItem } from "./groupTypes";
import { credentialDisplayLabel } from "./modelGroupFormatting";

function candidateSearchText(
  item: ModelGroupCandidateItem,
  locale: "zh-CN" | "en-US",
) {
  const credentialLabel = credentialDisplayLabel(
    {
      credential_name: item.credential_name,
      credential_number: item.credential_number,
    },
    locale,
  );
  const protocols = item.protocols
    .map((protocol) => protocolLabel(protocol, locale))
    .join(" ");
  return `${item.model_name} ${item.channel_name} ${protocols} ${credentialLabel} ${item.credential_name} ${item.base_url}`;
}

/** Compile a case-insensitive candidate search pattern when valid. */
export function compileCandidateRegex(value: string) {
  const trimmedValue = value.trim();
  const pattern = trimmedValue.startsWith("(?i)")
    ? trimmedValue.slice(4)
    : trimmedValue;
  try {
    return new RegExp(pattern, "i");
  } catch {
    return null;
  }
}

/** Return whether a candidate matches the selected search mode and query. */
export function matchesCandidateSearch(
  item: ModelGroupCandidateItem,
  mode: CandidateSearchMode,
  query: string,
  locale: "zh-CN" | "en-US",
) {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    return true;
  }
  if (mode === "regex") {
    const regex = compileCandidateRegex(trimmedQuery);
    if (!regex) {
      return false;
    }
    return regex.test(item.model_name);
  }
  return candidateSearchText(item, locale)
    .toLowerCase()
    .includes(trimmedQuery.toLowerCase());
}

/** Build the stable identity key for a model group member. */
export function modelGroupItemKey(
  item: Pick<FormItem, "channel_id" | "credential_id" | "model_name">,
) {
  return `${item.channel_id}::${item.credential_id}::${item.model_name}`;
}
