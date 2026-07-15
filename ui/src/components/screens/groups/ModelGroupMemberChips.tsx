import type { Dispatch, SetStateAction } from "react";
import { AlertCircle, Ban, GripVertical, X } from "lucide-react";
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
import {
  credentialDisplayLabel,
  modelGroupReasonsForState,
  modelGroupItemReasonLabel,
  type GroupRow,
} from "./modelGroupUtils";

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
    const sourceLabel = `${channelName} · ${credentialDisplayLabel(member, locale)}`;
    const enabled = member.enabled_item_count > 0;
    const invalidReasons = modelGroupReasonsForState(member.items, "invalid");
    const unavailableReasons = modelGroupReasonsForState(
      member.items,
      "unavailable",
    );
    const problemLabels = [...invalidReasons, ...unavailableReasons].map(
      (reason) => modelGroupItemReasonLabel(reason, locale),
    );
    return (
      <div
        key={`${member.key}::${index}`}
        className={cn(
          "flex min-w-0 max-w-full items-center rounded-full border bg-background",
          !enabled && !problemLabels.length && "opacity-55",
          problemLabels.length > 0 && "border-destructive/30 bg-destructive/5",
          cardDragging?.groupId === group.id &&
            cardDragging.index === index &&
            "opacity-60",
        )}
        title={`${sourceLabel} · ${member.model_name}${
          problemLabels.length ? ` · ${problemLabels.join(" · ")}` : ""
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
        {invalidReasons.length ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="destructive" className="mr-1" tabIndex={0}>
                <AlertCircle data-icon="inline-start" />
                {locale === "zh-CN" ? "配置错误" : "Invalid"}
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              {invalidReasons
                .map((reason) => modelGroupItemReasonLabel(reason, locale))
                .join(locale === "zh-CN" ? "、" : ", ")}
            </TooltipContent>
          </Tooltip>
        ) : null}
        {unavailableReasons.length ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="outline" className="mr-1" tabIndex={0}>
                <Ban data-icon="inline-start" />
                {locale === "zh-CN" ? "不可用" : "Unavailable"}
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              {unavailableReasons
                .map((reason) => modelGroupItemReasonLabel(reason, locale))
                .join(locale === "zh-CN" ? "、" : ", ")}
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
