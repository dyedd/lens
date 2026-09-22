import { toast } from "sonner";
import { ItemGroup } from "@/components/ui/Item";
import type { GroupsOverviewProps } from "./groupTypes";
import { ModelGroupCard } from "./ModelGroupCard";

export function ModelGroupList(
  props: Pick<
    GroupsOverviewProps,
    | "locale"
    | "isLoading"
    | "groupsIsError"
    | "visibleGroups"
    | "busyId"
    | "cardDragging"
    | "setCardDragging"
    | "effectiveSelectedModelPrefix"
    | "search"
    | "strategyFilter"
    | "openEdit"
    | "changeStrategy"
    | "reorderGroupMembers"
    | "reorderGroupChannels"
    | "removeGroupChannel"
    | "removeGroupMember"
    | "toggleGroupEnabled"
    | "setDeleteTarget"
    | "testingModel"
    | "openModelTest"
  >,
) {
  async function copyGroupName(name: string) {
    try {
      await navigator.clipboard.writeText(name);
      toast.success(
        props.locale === "zh-CN" ? "模型名称已复制" : "Model name copied",
      );
    } catch {
      toast.error(props.locale === "zh-CN" ? "复制失败" : "Failed to copy");
    }
  }

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/60 bg-background xl:min-h-[calc(100dvh-18rem)]">
      <div className="min-w-0 px-1 py-1 xl:max-h-[calc(100dvh-18rem)] xl:overflow-y-auto">
        {props.isLoading || props.groupsIsError ? null : props.visibleGroups
            .length ? (
          <ItemGroup className="gap-0">
            {props.visibleGroups.map((group) => (
              <ModelGroupCard
                key={group.id}
                {...props}
                group={group}
                copyGroupName={copyGroupName}
              />
            ))}
          </ItemGroup>
        ) : (
          <div className="px-6 py-12 text-center text-sm text-muted-foreground">
            {props.locale === "zh-CN"
              ? "没有匹配的模型组。"
              : "No matching groups."}
          </div>
        )}
      </div>
    </div>
  );
}
