import {
  canReachProtocol,
  type ModelGroup,
  type ModelGroupEnsureFromSiteResponse,
  type ModelGroupEnsureModelInput,
  type ModelGroupEnsureResultItem,
} from "@/lib/api";

export function modelGroupEnsureResultKey(item: ModelGroupEnsureResultItem) {
  return JSON.stringify([
    item.protocol_config_id,
    item.credential_id,
    item.model_name,
    item.protocols,
  ]);
}

export function canSubmitModelGroupEnsureItem(
  item: ModelGroupEnsureResultItem,
) {
  return item.status === "create" || item.status === "update";
}

export function executionModelGroups(groups: ModelGroup[]) {
  return groups.filter((group) => !group.route_group_id?.trim());
}

export function canUseModelGroupWithoutProtocolExtension(
  item: ModelGroupEnsureResultItem,
  group: ModelGroup,
) {
  return group.protocols.some((groupProtocol) =>
    item.protocols.some((itemProtocol) =>
      canReachProtocol(itemProtocol, groupProtocol),
    ),
  );
}

export function selectableModelGroupsForEnsureItem(
  item: ModelGroupEnsureResultItem,
  groups: ModelGroup[],
  allowProtocolExtension: boolean,
) {
  const executableGroups = executionModelGroups(groups);
  if (allowProtocolExtension) return executableGroups;
  return executableGroups.filter((group) =>
    canUseModelGroupWithoutProtocolExtension(item, group),
  );
}

export function modelGroupEnsureReasonLabel(reason: string, locale: string) {
  if (!reason) return locale === "zh-CN" ? "未知原因" : "Unknown reason";
  const labels: Record<string, { zh: string; en: string }> = {
    route_group: {
      zh: "同名模型组是路由组",
      en: "Same-name group is a route group",
    },
    duplicate_selection: {
      zh: "重复选择",
      en: "Duplicate selection",
    },
    model_name_required: {
      zh: "模型名称为空",
      en: "Model name is required",
    },
    group_name_required: {
      zh: "模型组名称为空",
      en: "Group name is required",
    },
    protocol_config_not_found: {
      zh: "组合不存在",
      en: "Combination not found",
    },
    channel_disabled: {
      zh: "渠道不可用",
      en: "Channel unavailable",
    },
    credential_not_found: {
      zh: "密钥不存在",
      en: "Key not found",
    },
    credential_disabled: {
      zh: "密钥已停用",
      en: "Key disabled",
    },
    model_not_available: {
      zh: "模型不可用",
      en: "Model unavailable",
    },
    protocol_extension_required: {
      zh: "需要扩展目标模型组协议",
      en: "Target group needs protocol extension",
    },
  };
  const label = labels[reason];
  return label ? (locale === "zh-CN" ? label.zh : label.en) : reason;
}

export function modelGroupEnsureSkippedToastMessage(
  result: ModelGroupEnsureFromSiteResponse,
  locale: string,
) {
  const skippedItems = result.items.filter((item) => item.status === "skipped");
  if (!skippedItems.length) return "";

  const reasonCounts = new Map<string, number>();
  for (const item of skippedItems) {
    const reason = item.skipped_reason || "unknown";
    reasonCounts.set(reason, (reasonCounts.get(reason) ?? 0) + 1);
  }
  const reasonSummary = Array.from(reasonCounts.entries())
    .slice(0, 2)
    .map(([reason, count]) => {
      const label = modelGroupEnsureReasonLabel(reason, locale);
      return count > 1 ? `${label} x${count}` : label;
    })
    .join(locale === "zh-CN" ? "，" : ", ");

  return locale === "zh-CN"
    ? `已跳过 ${skippedItems.length} 个模型：${reasonSummary}`
    : `Skipped ${skippedItems.length} models: ${reasonSummary}`;
}

export function modelGroupEnsureInputsFromResult(
  items: ModelGroupEnsureResultItem[],
  groupNameOverrides = new Map<string, string>(),
): ModelGroupEnsureModelInput[] {
  return items.map((item) => ({
    protocol_config_id: item.protocol_config_id,
    credential_id: item.credential_id,
    model_name: item.model_name,
    group_name:
      groupNameOverrides.get(modelGroupEnsureResultKey(item)) ??
      item.group_name,
    protocols: item.protocols,
  }));
}

export function suggestModelGroupName(modelName: string, groups: ModelGroup[]) {
  const normalizedModelName = modelName.trim();
  if (!normalizedModelName) return "";
  if (groups.some((group) => group.name === normalizedModelName)) {
    return normalizedModelName;
  }

  let bestMatch = "";
  for (const group of groups) {
    const groupName = group.name.trim();
    if (!groupName || groupName.length <= bestMatch.length) continue;
    if (!normalizedModelName.startsWith(groupName)) continue;
    const nextCharacter = normalizedModelName.charAt(groupName.length);
    if (nextCharacter && !["-", "_", ".", " ", ":"].includes(nextCharacter)) {
      continue;
    }
    bestMatch = groupName;
  }

  return bestMatch || normalizedModelName;
}
