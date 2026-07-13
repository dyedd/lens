"use client";

import { AlertCircle, Check, GripVertical, Plus, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Switch } from "@/components/ui/Switch";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { ModelGroupCandidateItem, ProtocolKind } from "@/lib/api";
import { isItemValidForProtocols } from "@/lib/api";
import { protocolBadgeClassName, protocolLabel } from "@/lib/protocols";
import { cn } from "@/lib/utils";
import { foldedMemberSourceLabel, type FoldedMember } from "./modelGroupUtils";

/** Render a selectable model group candidate. */
export function CandidateRow({
  candidate,
  active,
  selectedProtocols,
  locale,
  onClick,
}: {
  candidate: ModelGroupCandidateItem;
  active: boolean;
  selectedProtocols: ProtocolKind[];
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
        {nativeProtocols.map((protocol) => {
          const isUsable = isItemValidForProtocols(protocol, selectedProtocols);
          return (
            <Badge
              key={protocol}
              variant="outline"
              className={cn(
                "px-1.5 py-0 text-[10px] font-normal",
                isUsable
                  ? protocolBadgeClassName(protocol)
                  : "border-transparent bg-muted/50 text-muted-foreground/50",
              )}
            >
              {protocolLabel(protocol, locale)}
            </Badge>
          );
        })}
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
        !member.enabled && "opacity-55",
        member.invalid && "border border-destructive bg-destructive/10",
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
          {!member.enabled
            ? ` · ${locale === "zh-CN" ? "已关闭" : "Disabled"}`
            : ""}
        </div>
      </div>
      <div className="flex h-8 w-8 items-center justify-center">
        <Switch
          checked={member.enabled}
          disabled={isBusy}
          onCheckedChange={onToggle}
        />
      </div>
      {member.invalid ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="grid h-8 w-8 shrink-0 place-items-center text-destructive">
              <AlertCircle size={15} />
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {locale === "zh-CN"
              ? "不适用于当前所选的对外协议"
              : "Invalid for current protocols"}
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
