import type { ModelGroup, ModelGroupEnsureStatus } from "@/lib/api";
import type { Locale } from "./channelShared";

export function modelGroupEnsureStatusLabel(
  status: ModelGroupEnsureStatus,
  locale: Locale,
) {
  if (status === "create") return locale === "zh-CN" ? "新建" : "Create";
  if (status === "update") return locale === "zh-CN" ? "加入" : "Update";
  if (status === "unchanged") {
    return locale === "zh-CN" ? "已存在" : "Unchanged";
  }
  return locale === "zh-CN" ? "跳过" : "Skipped";
}

export function modelGroupEnsureStatusVariant(
  status: ModelGroupEnsureStatus,
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "create") return "default";
  if (status === "update") return "secondary";
  if (status === "skipped") return "destructive";
  return "outline";
}

export function nextCreateModelGroupName(
  modelName: string,
  modelGroups: ModelGroup[],
) {
  const groupNames = new Set(modelGroups.map((group) => group.name));
  if (!groupNames.has(modelName)) return modelName;
  for (let index = 1; ; index += 1) {
    const candidate = `${modelName}-${index}`;
    if (!groupNames.has(candidate)) return candidate;
  }
}
