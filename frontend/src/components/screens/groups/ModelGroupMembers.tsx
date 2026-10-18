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
import type { ModelGroupCandidateItem } from "@/lib/api/groups";
import { cn } from "@/lib/classNames";
import {
  contextWindowSourceLabel,
  formatContextWindow,
} from "@/lib/contextWindow";
import type { FoldedMember } from "./groupTypes";
import {
  formatCredentialIdentity,
  formatMemberSource,
  modelGroupItemReasonLabel,
  modelGroupReasonsForState,
} from "./modelGroupFormatting";

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
  return (
    <Button
      type="button"
      variant="ghost"
      className={cn(
        "h-auto min-h-8 w-full justify-between rounded-md px-2 py-1 text-left",
        active ? "cursor-not-allowed opacity-60" : "hover:bg-muted/50",
      )}
      onClick={onClick}
      disabled={active}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate font-mono text-xs font-medium text-foreground">
          {candidate.model_name}
        </div>
        <div className="truncate text-xs font-normal text-muted-foreground">
          {formatCredentialIdentity(candidate, locale, { includeSite: false })}
        </div>
      </div>
      <div className="flex min-w-0 shrink-0 flex-wrap items-center justify-end gap-1.5">
        <span className="text-muted-foreground">
          {active ? (
            <Check className="size-4 text-primary" />
          ) : (
            <Plus className="size-4" />
          )}
        </span>
      </div>
    </Button>
  );
}

/** Render a grouped model member with reorder and removal controls. */
export function FoldedMemberRow({
  member,
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
  const sourceLabel = formatCredentialIdentity(member, locale, {
    includeSite: showChannelName,
  });
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
    <li
      draggable={canReorder}
      onDragStart={canReorder ? onDragStart : undefined}
      onDragEnter={canReorder ? onDragEnter : undefined}
      onDragOver={canReorder ? (event) => event.preventDefault() : undefined}
      onDragEnd={canReorder ? onDragEnd : undefined}
      className={cn(
        "flex min-h-8 min-w-0 items-center gap-1.5 rounded-md px-1.5 py-1 transition-colors hover:bg-muted/50",
        isDragging && "opacity-60",
        !enabled && "opacity-55",
        (member.invalid_item_count > 0 || member.unavailable_item_count > 0) &&
          "border border-destructive/40 bg-destructive/10",
      )}
    >
      {canReorder ? (
        <span
          aria-hidden="true"
          className="grid size-5 shrink-0 cursor-grab place-items-center rounded-md text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground active:cursor-grabbing"
        >
          <GripVertical className="size-3.5" />
        </span>
      ) : null}
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1">
        <div className="min-w-0 flex-1">
          <div className="truncate font-mono text-xs font-medium text-foreground">
            {member.model_name}
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="truncate text-xs text-muted-foreground">
                {sourceLabel}
                {partiallyEnabled
                  ? ` · ${locale === "zh-CN" ? "部分启用" : "Partially enabled"}`
                  : !manuallyEnabled
                    ? ` · ${locale === "zh-CN" ? "已关闭" : "Disabled"}`
                    : ""}
              </div>
            </TooltipTrigger>
            <TooltipContent className="max-w-sm break-all">
              {sourceLabel}
            </TooltipContent>
          </Tooltip>
        </div>
        <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-1">
          {member.source !== "manual" ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="outline" tabIndex={0}>
                  {formatMemberSource(member.source, locale)}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                {locale === "zh-CN"
                  ? "匹配组规则或同名的模型在保存和同步时自动加入；可以像其他成员一样拖动排序"
                  : "Joined automatically when the names match; reorder it like any member"}
              </TooltipContent>
            </Tooltip>
          ) : null}
          {member.rate_source !== "none" &&
          typeof member.rate_multiplier === "number" ? (
            <Badge variant="secondary">
              {locale === "zh-CN" ? "倍率" : "Rate"} {member.rate_multiplier}x
            </Badge>
          ) : null}
          {member.context_window !== null ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="secondary" tabIndex={0}>
                  {locale === "zh-CN" ? "上下文" : "Context"}{" "}
                  {formatContextWindow(member.context_window)}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>
                {member.context_window_source
                  ? `${contextWindowSourceLabel(member.context_window_source, locale)} · `
                  : ""}
                {member.context_window.toLocaleString()} tokens
              </TooltipContent>
            </Tooltip>
          ) : null}
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
                <Badge variant="secondary" tabIndex={0}>
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
        </div>
      </div>
      <div className="flex size-7 shrink-0 items-center justify-center">
        <Switch
          checked={enabled}
          disabled={isBusy || automaticallyUnavailable}
          onCheckedChange={onToggle}
          aria-label={
            locale === "zh-CN" ? "切换成员启用状态" : "Toggle member status"
          }
        />
      </div>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            className="text-muted-foreground"
            size="icon-xs"
            aria-label={locale === "zh-CN" ? "移除成员" : "Remove member"}
            onClick={onRemove}
          >
            <X className="size-3.5" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {member.source !== "manual"
            ? locale === "zh-CN"
              ? "移除后不再自动加入，可在“已排除”中恢复"
              : "It will no longer join automatically; restore it from Excluded"
            : locale === "zh-CN"
              ? "移除成员"
              : "Remove member"}
        </TooltipContent>
      </Tooltip>
    </li>
  );
}
