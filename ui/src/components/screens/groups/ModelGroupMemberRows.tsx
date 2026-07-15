"use client";

import {
  AlertCircle,
  Ban,
  Check,
  Clock3,
  GripVertical,
  Plus,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Switch } from "@/components/ui/Switch";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { ModelGroupCandidateItem } from "@/lib/api";
import { protocolBadgeClassName, protocolLabel } from "@/lib/protocols";
import { cn } from "@/lib/utils";
import {
  foldedMemberSourceLabel,
  modelGroupReasonsForState,
  modelGroupItemReasonLabel,
  type FoldedMember,
} from "./modelGroupUtils";

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
  locale: "zh-CN" | "en-US";
}) {
  const sourceLabel = foldedMemberSourceLabel(member, locale);
  const enabled = member.enabled_item_count > 0;
  const partiallyEnabled = enabled && member.disabled_item_count > 0;
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
        ? `部分不可用 ${member.unavailable_item_count}`
        : `Partly unavailable ${member.unavailable_item_count}`
      : locale === "zh-CN"
        ? "不可用"
        : "Unavailable";

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
      <span
        className={cn(
          "text-muted-foreground",
          canReorder ? "cursor-grab active:cursor-grabbing" : "opacity-30",
        )}
      >
        <GripVertical size={14} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">
          {member.model_name}
        </div>
        <div className="truncate text-xs text-muted-foreground">
          {sourceLabel}
          {partiallyEnabled
            ? ` · ${locale === "zh-CN" ? "部分启用" : "Partially enabled"}`
            : !enabled
              ? ` · ${locale === "zh-CN" ? "已关闭" : "Disabled"}`
              : ""}
        </div>
      </div>
      <div className="flex h-8 w-8 items-center justify-center">
        <Switch
          checked={enabled}
          disabled={isBusy}
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
        variant="ghost"
        size="icon"
        className="text-muted-foreground hover:text-destructive"
        onClick={onRemove}
      >
        <X size={13} />
      </Button>
    </div>
  );
}
