import {
  AlertCircle,
  Ban,
  Check,
  Clock3,
  GripVertical,
  Plus,
  X,
} from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ItemDescription } from "@/components/ui/Item";
import { Switch } from "@/components/ui/Switch";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { ModelGroupCandidateItem } from "@/lib/api/groups";
import { cn } from "@/lib/classNames";
import { protocolBadgeClassName, protocolLabel } from "@/lib/protocols";
import type { FoldedMember, GroupCardDragging, GroupRow } from "./groupTypes";
import {
  credentialDisplayLabel,
  foldedMemberSourceLabel,
  modelGroupItemReasonLabel,
  modelGroupReasonsForState,
} from "./modelGroupFormatting";

interface ModelGroupMembersProps {
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
  reorderGroupChannels: (
    group: GroupRow,
    fromIndex: number,
    toIndex: number,
  ) => void;
  removeGroupChannel: (group: GroupRow, channelKey: string) => void;
  removeGroupMember: (group: GroupRow, memberKey: string) => void;
}

/** Render route targets or draggable members for a model group card. */
export function ModelGroupMembers({
  group,
  locale,
  busyId,
  cardDragging,
  setCardDragging,
  reorderGroupMembers,
  reorderGroupChannels,
  removeGroupChannel,
  removeGroupMember,
}: ModelGroupMembersProps) {
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

  if (group.strategy === "failover") {
    return group.display_channels.map((channel, index) => {
      const hasEnabledMember = channel.members.some(
        (member) => member.ready_item_count > 0,
      );
      const hasProblem = channel.members.some(
        (member) =>
          member.invalid_item_count > 0 || member.unavailable_item_count > 0,
      );
      const modelNames = channel.members
        .map((member) => member.model_name)
        .join(" · ");
      return (
        <div
          key={channel.key}
          className={cn(
            "flex min-w-0 max-w-full items-center rounded-full border bg-background",
            !hasEnabledMember && !hasProblem && "opacity-55",
            hasProblem && "border-destructive/30 bg-destructive/5",
            cardDragging?.groupId === group.id &&
              cardDragging.kind === "channel" &&
              cardDragging.index === index &&
              "opacity-60",
          )}
          title={`${channel.channel_name || channel.channel_id} · ${modelNames}`}
        >
          <Button
            type="button"
            variant="ghost"
            size="sm"
            draggable={busyId !== group.id}
            className="h-auto min-w-0 max-w-full cursor-grab rounded-full rounded-r-none border-0 px-3 py-1.5 active:cursor-grabbing"
            onDragStart={() =>
              setCardDragging({ groupId: group.id, kind: "channel", index })
            }
            onDragOver={(event) => event.preventDefault()}
            onDrop={() => {
              if (
                !cardDragging ||
                cardDragging.groupId !== group.id ||
                cardDragging.kind !== "channel"
              ) {
                return;
              }
              void reorderGroupChannels(group, cardDragging.index, index);
            }}
            onDragEnd={() => setCardDragging(null)}
          >
            <GripVertical data-icon="inline-start" />
            <span className="min-w-0 truncate">
              {channel.channel_name || channel.channel_id || "n/a"}
            </span>
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="icon-xs"
            className="mr-1 shrink-0 rounded-full"
            disabled={busyId === group.id}
            aria-label={
              locale === "zh-CN" ? "移除整个渠道" : "Remove entire channel"
            }
            title={
              locale === "zh-CN" ? "移除整个渠道" : "Remove entire channel"
            }
            onClick={() => void removeGroupChannel(group, channel.key)}
          >
            <X />
          </Button>
        </div>
      );
    });
  }

  return group.display_members.map((member, index) => {
    const channelName = member.channel_names.slice(0, 2).join(" · ") || "n/a";
    const sourceLabel = `${channelName} · ${credentialDisplayLabel(member, locale)}`;
    const enabled = member.ready_item_count > 0;
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
            cardDragging.kind === "member" &&
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
          onDragStart={() =>
            setCardDragging({ groupId: group.id, kind: "member", index })
          }
          onDragOver={(event) => event.preventDefault()}
          onDrop={() => {
            if (
              !cardDragging ||
              cardDragging.groupId !== group.id ||
              cardDragging.kind !== "member"
            ) {
              return;
            }
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
                {locale === "zh-CN" ? "依赖不可用" : "Dependency unavailable"}
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
          variant="destructive"
          size="icon-xs"
          className="mr-1 shrink-0 rounded-full"
          aria-label={locale === "zh-CN" ? "移除成员" : "Remove member"}
          title={locale === "zh-CN" ? "移除成员" : "Remove member"}
          disabled={busyId === group.id}
          onClick={() => void removeGroupMember(group, member.key)}
        >
          <X />
        </Button>
      </div>
    );
  });
}

/** Render a selectable model group candidate. */
export function CandidateRow({
  candidate,
  active,
  locale,
  onClick,
}: {
  candidate: ModelGroupCandidateItem;
  active: boolean;
  locale: "zh-CN" | "en-US";
  onClick: () => void;
}) {
  const nativeProtocols = candidate.protocols;

  return (
    <Button
      type="button"
      variant="ghost"
      className={cn(
        "h-auto min-h-8 w-full justify-between rounded-md px-3 py-1.5 text-left",
        active ? "cursor-not-allowed opacity-60" : "hover:bg-muted",
      )}
      onClick={onClick}
      disabled={active}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">
          {candidate.model_name}
        </div>
      </div>
      <div className="flex min-w-0 shrink-0 flex-wrap items-center justify-end gap-1.5">
        {nativeProtocols.map((protocol) => (
          <Badge
            key={protocol}
            variant="outline"
            className={cn(
              "px-1.5 py-0 text-[10px] font-normal",
              protocolBadgeClassName(protocol),
            )}
          >
            {protocolLabel(protocol, locale)}
          </Badge>
        ))}
        <span className="text-muted-foreground">
          {active ? (
            <Check size={15} className="text-primary" />
          ) : (
            <Plus size={15} />
          )}
        </span>
      </div>
    </Button>
  );
}

/** Render a grouped model member with reorder and removal controls. */
export function FoldedMemberRow({
  member,
  index,
  isDragging,
  isBusy,
  canReorder,
  onToggle,
  onRemove,
  onDragStart,
  onDragEnter,
  onDragEnd,
  showChannelName = true,
  locale,
}: {
  member: FoldedMember;
  index: number;
  isDragging: boolean;
  isBusy: boolean;
  canReorder: boolean;
  onToggle: () => void;
  onRemove: () => void;
  onDragStart: () => void;
  onDragEnter: () => void;
  onDragEnd: () => void;
  showChannelName?: boolean;
  locale: "zh-CN" | "en-US";
}) {
  const sourceLabel = showChannelName
    ? foldedMemberSourceLabel(member, locale)
    : credentialDisplayLabel(member, locale);
  const enabled = member.ready_item_count > 0;
  const manuallyEnabled = member.enabled_item_count > 0;
  const partiallyEnabled = manuallyEnabled && member.disabled_item_count > 0;
  const automaticallyUnavailable = !enabled && manuallyEnabled;
  const invalidReasons = modelGroupReasonsForState(member.subItems, "invalid");
  const unavailableReasons = modelGroupReasonsForState(
    member.subItems,
    "unavailable",
  );
  const invalidLabel =
    member.invalid_item_count < member.subItems.length
      ? locale === "zh-CN"
        ? `部分配置错误 ${member.invalid_item_count}`
        : `Partly invalid ${member.invalid_item_count}`
      : locale === "zh-CN"
        ? "配置错误"
        : "Invalid";
  const unavailableLabel =
    member.unavailable_item_count < member.subItems.length
      ? locale === "zh-CN"
        ? `部分依赖不可用 ${member.unavailable_item_count}`
        : `Dependencies unavailable ${member.unavailable_item_count}`
      : locale === "zh-CN"
        ? "依赖不可用"
        : "Dependency unavailable";

  return (
    <div
      draggable={canReorder}
      onDragStart={canReorder ? onDragStart : undefined}
      onDragEnter={canReorder ? onDragEnter : undefined}
      onDragOver={canReorder ? (event) => event.preventDefault() : undefined}
      onDragEnd={canReorder ? onDragEnd : undefined}
      className={cn(
        "flex min-w-0 items-center gap-2 border-b px-2.5 py-2 transition last:border-b-0",
        isDragging && "opacity-60 shadow-sm",
        !enabled && "opacity-55",
        (member.invalid_item_count > 0 || member.unavailable_item_count > 0) &&
          "border border-destructive bg-destructive/10",
      )}
    >
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
        {index + 1}
      </span>
      {canReorder ? (
        <span className="cursor-grab text-muted-foreground active:cursor-grabbing">
          <GripVertical size={14} />
        </span>
      ) : null}
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">
          {member.model_name}
        </div>
        <div className="truncate text-xs text-muted-foreground">
          {sourceLabel}
          {partiallyEnabled
            ? ` · ${locale === "zh-CN" ? "部分启用" : "Partially enabled"}`
            : !manuallyEnabled
              ? ` · ${locale === "zh-CN" ? "已关闭" : "Disabled"}`
              : ""}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
        {member.rate_source !== "none" &&
        typeof member.rate_multiplier === "number" ? (
          <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
            {locale === "zh-CN" ? "倍率" : "Rate"} {member.rate_multiplier}x
          </Badge>
        ) : null}
        {member.protocols.map((protocol) => (
          <Badge
            key={protocol}
            variant="outline"
            className={cn(
              "px-1.5 py-0 text-[10px] font-normal",
              protocolBadgeClassName(protocol),
            )}
          >
            {protocolLabel(protocol, locale)}
          </Badge>
        ))}
      </div>
      <div className="flex h-8 w-8 items-center justify-center">
        <Switch
          checked={enabled}
          disabled={isBusy || automaticallyUnavailable}
          onCheckedChange={onToggle}
          aria-label={
            locale === "zh-CN" ? "切换成员启用状态" : "Toggle member status"
          }
        />
      </div>
      {member.pending_item_count > 0 ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="outline" tabIndex={0}>
              <Clock3 data-icon="inline-start" />
              {locale === "zh-CN" ? "检查中" : "Checking"}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            {locale === "zh-CN"
              ? "等待后端返回最新状态"
              : "Waiting for the latest backend evaluation"}
          </TooltipContent>
        </Tooltip>
      ) : null}
      {member.invalid_item_count > 0 ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="destructive" tabIndex={0}>
              <AlertCircle data-icon="inline-start" />
              {invalidLabel}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            {invalidReasons
              .map((reason) => modelGroupItemReasonLabel(reason, locale))
              .join(locale === "zh-CN" ? "、" : ", ")}
          </TooltipContent>
        </Tooltip>
      ) : null}
      {member.unavailable_item_count > 0 ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="outline" tabIndex={0}>
              <Ban data-icon="inline-start" />
              {unavailableLabel}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            {unavailableReasons
              .map((reason) => modelGroupItemReasonLabel(reason, locale))
              .join(locale === "zh-CN" ? "、" : ", ")}
          </TooltipContent>
        </Tooltip>
      ) : null}
      <Button
        type="button"
        variant="destructive"
        size="icon"
        aria-label={locale === "zh-CN" ? "移除成员" : "Remove member"}
        title={locale === "zh-CN" ? "移除成员" : "Remove member"}
        onClick={onRemove}
      >
        <X size={13} />
      </Button>
    </div>
  );
}
