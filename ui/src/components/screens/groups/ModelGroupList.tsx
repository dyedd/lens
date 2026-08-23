import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/Card";
import { ItemGroup } from "@/components/ui/Item";
import type { GroupsOverviewProps } from "./groupOverviewTypes";
import { ModelGroupCard } from "./ModelGroupCard";

type ModelGroupListProps = Pick<
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
>;

/** Render the filtered model group cards or the matching empty state. */
export function ModelGroupList(props: ModelGroupListProps) {
  const {
    locale,
    isLoading,
    groupsIsError,
    visibleGroups,
    effectiveSelectedModelPrefix,
    search,
    strategyFilter,
  } = props;

  async function copyGroupName(name: string) {
    try {
      await navigator.clipboard.writeText(name);
      toast.success(
        locale === "zh-CN" ? "模型名称已复制" : "Model name copied",
      );
    } catch {
      toast.error(locale === "zh-CN" ? "复制失败" : "Failed to copy");
    }
  }

  return (
    <Card className="min-w-0 overflow-hidden py-0 xl:min-h-[calc(100dvh-18rem)]">
      <CardContent className="min-w-0 px-3 py-3 xl:max-h-[calc(100dvh-18rem)] xl:overflow-y-auto">
        {isLoading || groupsIsError ? null : visibleGroups.length ? (
          <ItemGroup className="gap-3">
            {visibleGroups.map((group) => (
              <ModelGroupCard
                key={group.id}
                group={group}
                locale={locale}
                busyId={props.busyId}
                cardDragging={props.cardDragging}
                setCardDragging={props.setCardDragging}
                openEdit={props.openEdit}
                copyGroupName={copyGroupName}
                changeStrategy={props.changeStrategy}
                reorderGroupMembers={props.reorderGroupMembers}
                reorderGroupChannels={props.reorderGroupChannels}
                removeGroupChannel={props.removeGroupChannel}
                removeGroupMember={props.removeGroupMember}
                toggleGroupEnabled={props.toggleGroupEnabled}
                setDeleteTarget={props.setDeleteTarget}
                testingModel={props.testingModel}
                openModelTest={props.openModelTest}
              />
            ))}
          </ItemGroup>
        ) : (
          <div className="rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground">
            {effectiveSelectedModelPrefix !== "all" ||
            search.trim() ||
            strategyFilter !== "all"
              ? locale === "zh-CN"
                ? "没有匹配的模型组。"
                : "No matching groups."
              : locale === "zh-CN"
                ? "当前还没有模型组。"
                : "No groups yet."}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
