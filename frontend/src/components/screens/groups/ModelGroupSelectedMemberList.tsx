import { GripVertical } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Switch } from "@/components/ui/Switch";
import type { RoutingStrategy } from "@/lib/api/groups";
import { cn } from "@/lib/classNames";
import type {
  ChannelMemberGroup,
  FoldedMember,
  MemberStatusFilter,
} from "./groupTypes";
import { FoldedMemberRow } from "./ModelGroupMemberRows";

interface ModelGroupSelectedMemberListProps {
  locale: "zh-CN" | "en-US";
  strategy: RoutingStrategy;
  memberStatusFilter: MemberStatusFilter;
  visibleFoldedMembers: Array<{ member: FoldedMember; index: number }>;
  visibleChannelGroups: ChannelMemberGroup[];
  toggleChannelMembers: (channelKey: string, enabled: boolean) => void;
  toggleFoldedMember: (foldKey: string, enabled: boolean) => void;
  removeFoldedMember: (foldKey: string) => void;
  moveChannelGroup: (fromIndex: number, toIndex: number) => void;
  moveFoldedMember: (fromIndex: number, toIndex: number) => void;
  moveFoldedMemberWithinChannel: (
    channelKey: string,
    fromIndex: number,
    toIndex: number,
  ) => void;
}

type SelectedMemberRowProps = {
  locale: "zh-CN" | "en-US";
  member: FoldedMember;
  index: number;
  canReorder: boolean;
  showChannelName: boolean;
  isDragging: boolean;
  onDragStart: () => void;
  onDragEnter: () => void;
  onDragEnd: () => void;
  toggleFoldedMember: (foldKey: string, enabled: boolean) => void;
  removeFoldedMember: (foldKey: string) => void;
};

function SelectedMemberRow({
  locale,
  member,
  index,
  canReorder,
  showChannelName,
  isDragging,
  onDragStart,
  onDragEnter,
  onDragEnd,
  toggleFoldedMember,
  removeFoldedMember,
}: SelectedMemberRowProps) {
  return (
    <FoldedMemberRow
      member={member}
      index={index}
      isDragging={isDragging}
      isBusy={false}
      canReorder={canReorder}
      onToggle={() =>
        toggleFoldedMember(member.key, member.enabled_item_count === 0)
      }
      onRemove={() => removeFoldedMember(member.key)}
      onDragStart={onDragStart}
      onDragEnter={onDragEnter}
      onDragEnd={onDragEnd}
      showChannelName={showChannelName}
      locale={locale}
    />
  );
}

type RoundRobinMemberListProps = Pick<
  ModelGroupSelectedMemberListProps,
  | "locale"
  | "visibleFoldedMembers"
  | "toggleFoldedMember"
  | "removeFoldedMember"
  | "moveFoldedMember"
> & { canReorder: boolean };

function RoundRobinMemberList({
  locale,
  visibleFoldedMembers,
  toggleFoldedMember,
  removeFoldedMember,
  moveFoldedMember,
  canReorder,
}: RoundRobinMemberListProps) {
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);

  return (
    <div className="flex flex-col gap-1.5">
      {visibleFoldedMembers.map(({ member, index }) => (
        <SelectedMemberRow
          key={member.key}
          locale={locale}
          member={member}
          index={index}
          canReorder={canReorder}
          showChannelName
          isDragging={canReorder && draggingIndex === index}
          onDragStart={() => setDraggingIndex(index)}
          onDragEnter={() => {
            if (draggingIndex === null || draggingIndex === index) return;
            moveFoldedMember(draggingIndex, index);
            setDraggingIndex(index);
          }}
          onDragEnd={() => setDraggingIndex(null)}
          toggleFoldedMember={toggleFoldedMember}
          removeFoldedMember={removeFoldedMember}
        />
      ))}
    </div>
  );
}

type FailoverMemberListProps = Pick<
  ModelGroupSelectedMemberListProps,
  | "locale"
  | "visibleChannelGroups"
  | "toggleChannelMembers"
  | "toggleFoldedMember"
  | "removeFoldedMember"
  | "moveChannelGroup"
  | "moveFoldedMemberWithinChannel"
> & { canReorder: boolean };

function FailoverMemberList({
  locale,
  visibleChannelGroups,
  toggleChannelMembers,
  toggleFoldedMember,
  removeFoldedMember,
  moveChannelGroup,
  moveFoldedMemberWithinChannel,
  canReorder,
}: FailoverMemberListProps) {
  const [draggingChannelIndex, setDraggingChannelIndex] = useState<
    number | null
  >(null);
  const [draggingChannelMember, setDraggingChannelMember] = useState<{
    channelKey: string;
    index: number;
  } | null>(null);

  return (
    <div className="flex flex-col gap-2">
      {visibleChannelGroups.map((channelGroup, channelIndex) => (
        <div
          key={channelGroup.key}
          className="overflow-hidden rounded-md border bg-background/40"
        >
          <div
            onDragEnter={
              canReorder
                ? () => {
                    if (
                      draggingChannelIndex === null ||
                      draggingChannelIndex === channelIndex
                    ) {
                      return;
                    }
                    moveChannelGroup(draggingChannelIndex, channelIndex);
                    setDraggingChannelIndex(channelIndex);
                  }
                : undefined
            }
            onDragOver={
              canReorder ? (event) => event.preventDefault() : undefined
            }
            className={cn(
              "flex min-h-10 min-w-0 items-center gap-2 bg-muted/40 px-3 py-2",
              draggingChannelIndex === channelIndex && "opacity-60",
            )}
          >
            {canReorder ? (
              <span
                draggable
                className="cursor-grab text-muted-foreground active:cursor-grabbing"
                onDragStart={() => setDraggingChannelIndex(channelIndex)}
                onDragEnd={() => setDraggingChannelIndex(null)}
              >
                <GripVertical size={14} />
              </span>
            ) : null}
            <div className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
              {channelGroup.channel_name ||
                channelGroup.channel_id ||
                (locale === "zh-CN" ? "未知渠道" : "Unknown channel")}
            </div>
            <Switch
              checked={channelGroup.members.some(
                ({ member }) => member.ready_item_count > 0,
              )}
              disabled={
                !channelGroup.members.some(
                  ({ member }) => member.ready_item_count > 0,
                ) &&
                channelGroup.members.some(
                  ({ member }) => member.enabled_item_count > 0,
                )
              }
              aria-label={
                locale === "zh-CN"
                  ? `启停渠道 ${channelGroup.channel_name || channelGroup.channel_id}`
                  : `Toggle channel ${channelGroup.channel_name || channelGroup.channel_id}`
              }
              onCheckedChange={(enabled) =>
                toggleChannelMembers(channelGroup.key, enabled)
              }
            />
            <Badge
              variant="secondary"
              aria-label={`${locale === "zh-CN" ? "优先级" : "Priority"} ${channelGroup.priority}`}
              title={`${locale === "zh-CN" ? "优先级" : "Priority"} ${channelGroup.priority}`}
            >
              {channelGroup.priority}
            </Badge>
          </div>
          <div className="flex flex-col">
            {channelGroup.members.map(({ member }, memberIndex) => (
              <SelectedMemberRow
                key={member.key}
                locale={locale}
                member={member}
                index={memberIndex}
                canReorder={canReorder}
                showChannelName={false}
                isDragging={
                  canReorder &&
                  draggingChannelMember?.channelKey === channelGroup.key &&
                  draggingChannelMember.index === memberIndex
                }
                onDragStart={() =>
                  setDraggingChannelMember({
                    channelKey: channelGroup.key,
                    index: memberIndex,
                  })
                }
                onDragEnter={() => {
                  if (
                    draggingChannelMember?.channelKey !== channelGroup.key ||
                    draggingChannelMember.index === memberIndex
                  ) {
                    return;
                  }
                  moveFoldedMemberWithinChannel(
                    channelGroup.key,
                    draggingChannelMember.index,
                    memberIndex,
                  );
                  setDraggingChannelMember({
                    channelKey: channelGroup.key,
                    index: memberIndex,
                  });
                }}
                onDragEnd={() => setDraggingChannelMember(null)}
                toggleFoldedMember={toggleFoldedMember}
                removeFoldedMember={removeFoldedMember}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function emptyMemberListMessage(
  memberStatusFilter: MemberStatusFilter,
  locale: "zh-CN" | "en-US",
) {
  if (locale === "zh-CN") {
    return {
      all: "暂无已选模型",
      enabled: "没有包含启用项的模型",
      disabled: "没有包含关闭项的模型",
      problem: "没有需处理的模型",
    }[memberStatusFilter];
  }
  return {
    all: "No selected models",
    enabled: "No models with enabled items",
    disabled: "No models with disabled items",
    problem: "No models needing attention",
  }[memberStatusFilter];
}

/** Render selected members using the ordering implied by the routing strategy. */
export function ModelGroupSelectedMemberList(
  props: ModelGroupSelectedMemberListProps,
) {
  const canReorder = props.memberStatusFilter === "all";
  if (!props.visibleFoldedMembers.length) {
    return (
      <p className="px-1 py-6 text-center text-sm text-muted-foreground">
        {emptyMemberListMessage(props.memberStatusFilter, props.locale)}
      </p>
    );
  }
  if (props.strategy === "round_robin") {
    return <RoundRobinMemberList {...props} canReorder={canReorder} />;
  }
  return <FailoverMemberList {...props} canReorder={canReorder} />;
}
