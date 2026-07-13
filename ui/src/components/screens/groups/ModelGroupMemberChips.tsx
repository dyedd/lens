import type { Dispatch, SetStateAction } from "react";
import { GripVertical, TriangleAlert, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ItemDescription } from "@/components/ui/Item";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { cn } from "@/lib/utils";
import type { GroupCardDragging } from "./groupOverviewTypes";
import { credentialNumberLabel, type GroupRow } from "./modelGroupUtils";

interface ModelGroupMemberChipsProps {
  group: GroupRow;
  locale: "zh-CN" | "en-US";
  busyId: string | null;
  cardDragging: GroupCardDragging;
  setCardDragging: Dispatch<SetStateAction<GroupCardDragging>>;
  reorderGroupMembers: (
    group: GroupRow,
    fromIndex: number,
    toIndex: number,
  ) => void;
  removeGroupMember: (group: GroupRow, memberKey: string) => void;
  unavailableMemberStatusLabel: string;
  unavailableMemberTooltip: string;
}

/** Render route targets or draggable members for a model group card. */
export function ModelGroupMemberChips({
  group,
  locale,
  busyId,
  cardDragging,
  setCardDragging,
  reorderGroupMembers,
  removeGroupMember,
  unavailableMemberStatusLabel,
  unavailableMemberTooltip,
}: ModelGroupMemberChipsProps) {
  if (group.is_route_group) {
    return (
      <Badge variant="outline" className="px-3 py-1.5">
        {group.route_group_name || group.route_group_id || "n/a"}
      </Badge>
    );
  }

  if (!group.display_members.length) {
    return (
      <ItemDescription className="text-sm">
        {locale === "zh-CN" ? "暂无成员" : "No members"}
      </ItemDescription>
    );
  }

  return group.display_members.map((member, index) => {
    const channelName = member.channel_names.slice(0, 2).join(" · ") || "n/a";
    const sourceLabel = `${channelName} · ${credentialNumberLabel(member, locale)}`;
    return (
      <div
        key={`${member.key}::${index}`}
        className={cn(
          "flex min-w-0 max-w-full items-center rounded-full border bg-background",
          !member.enabled && !member.isUnavailable && "opacity-55",
          member.isUnavailable && "border-destructive/30 bg-destructive/5",
          cardDragging?.groupId === group.id &&
            cardDragging.index === index &&
            "opacity-60",
        )}
        title={`${sourceLabel} · ${member.model_name}${
          member.isUnavailable ? ` · ${unavailableMemberStatusLabel}` : ""
        }`}
      >
        <Button
          type="button"
          variant="ghost"
          size="sm"
          draggable={busyId !== group.id}
          className="h-auto min-w-0 max-w-full cursor-grab rounded-full rounded-r-none border-0 px-3 py-1.5 active:cursor-grabbing"
          onDragStart={() => setCardDragging({ groupId: group.id, index })}
          onDragOver={(event) => event.preventDefault()}
          onDrop={() => {
            if (!cardDragging || cardDragging.groupId !== group.id) return;
            void reorderGroupMembers(group, cardDragging.index, index);
          }}
          onDragEnd={() => setCardDragging(null)}
        >
          <GripVertical data-icon="inline-start" />
          <span className="min-w-0 truncate">{member.model_name}</span>
          <span className="min-w-0 truncate text-muted-foreground">
            · {sourceLabel}
          </span>
        </Button>
        {member.isUnavailable ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="destructive" className="mr-1" tabIndex={0}>
                <TriangleAlert data-icon="inline-start" />
                {unavailableMemberStatusLabel}
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              {unavailableMemberTooltip}
            </TooltipContent>
          </Tooltip>
        ) : null}
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          className="mr-1 shrink-0 rounded-full text-muted-foreground hover:text-destructive"
          disabled={busyId === group.id}
          onClick={() => void removeGroupMember(group, member.key)}
        >
          <X />
        </Button>
      </div>
    );
  });
}
