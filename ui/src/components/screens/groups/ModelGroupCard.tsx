import { createElement, type Dispatch, type SetStateAction } from "react";
import { Copy, Trash2, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemFooter,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/Item";
import { Switch } from "@/components/ui/Switch";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { ModelGroup, RoutingStrategy } from "@/lib/api";
import { getModelGroupAvatar } from "@/lib/ModelIcons";
import { protocolBadgeClassName, protocolLabel } from "@/lib/protocols";
import { cn } from "@/lib/utils";
import type { GroupCardDragging } from "./groupOverviewTypes";
import { CompactPriceSummary, StrategyToggle } from "./ModelGroupEditorFields";
import { ModelGroupMemberChips } from "./ModelGroupMemberChips";
import { isGroupEnabled, type GroupRow } from "./modelGroupUtils";

interface ModelGroupCardProps {
  group: GroupRow;
  locale: "zh-CN" | "en-US";
  busyId: string | null;
  cardDragging: GroupCardDragging;
  setCardDragging: Dispatch<SetStateAction<GroupCardDragging>>;
  openEdit: (item: ModelGroup) => void;
  copyGroupName: (name: string) => void;
  changeStrategy: (group: GroupRow, strategy: RoutingStrategy) => void;
  reorderGroupMembers: (
    group: GroupRow,
    fromIndex: number,
    toIndex: number,
  ) => void;
  removeGroupMember: (group: GroupRow, memberKey: string) => void;
  toggleGroupEnabled: (group: GroupRow, enabled: boolean) => void;
  setDeleteTarget: Dispatch<SetStateAction<ModelGroup | null>>;
}

/** Render a model group summary and its inline actions. */
export function ModelGroupCard({
  group,
  locale,
  busyId,
  cardDragging,
  setCardDragging,
  openEdit,
  copyGroupName,
  changeStrategy,
  reorderGroupMembers,
  removeGroupMember,
  toggleGroupEnabled,
  setDeleteTarget,
}: ModelGroupCardProps) {
  const copyModelNameLabel =
    locale === "zh-CN" ? "复制模型名称" : "Copy model name";
  const unavailableMemberStatusLabel = locale === "zh-CN" ? "失效" : "Invalid";
  const unavailableMemberTooltip =
    locale === "zh-CN"
      ? "成员关联的目标模型组、渠道、Base URL、密钥或模型不可用"
      : "Member references an unavailable route target, channel, base URL, key, or model";
  const unavailableMembersLabel =
    locale === "zh-CN"
      ? `包含 ${group.unavailable_member_count} 个失效成员`
      : `${group.unavailable_member_count} invalid ${
          group.unavailable_member_count === 1 ? "member" : "members"
        }`;

  return (
    <Item
      variant="outline"
      role="button"
      tabIndex={0}
      className="cursor-pointer items-start gap-3 rounded-2xl border-border/80 bg-background px-4 py-4 shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      onClick={() => openEdit(group)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openEdit(group);
        }
      }}
    >
      <ItemMedia
        variant="icon"
        className="mt-0.5 hidden size-11 self-start rounded-xl bg-muted/40 sm:flex"
      >
        {createElement(getModelGroupAvatar(group.name), { size: 30 })}
      </ItemMedia>
      <ItemContent className="min-w-0">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <ItemTitle className="truncate text-base">{group.name}</ItemTitle>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label={copyModelNameLabel}
                  className="-ml-1 text-muted-foreground hover:text-foreground"
                  onClick={(event) => {
                    event.stopPropagation();
                    void copyGroupName(group.name);
                  }}
                  onKeyDown={(event) => event.stopPropagation()}
                >
                  <Copy />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom" align="start">
                {copyModelNameLabel}
              </TooltipContent>
            </Tooltip>
            <div className="flex flex-wrap gap-1.5">
              {group.protocols.map((protocol) => (
                <Badge
                  key={protocol}
                  variant="outline"
                  className={cn(
                    "px-2.5 py-0.5",
                    protocolBadgeClassName(protocol),
                  )}
                >
                  {protocolLabel(protocol, locale)}
                </Badge>
              ))}
            </div>
            {group.is_route_group ? (
              <Badge variant="outline" className="px-2.5 py-0.5">
                {locale === "zh-CN" ? "路由组" : "Route group"}
              </Badge>
            ) : null}
            {group.unavailable_member_count > 0 ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge
                    variant="destructive"
                    className="px-2.5 py-0.5"
                    tabIndex={0}
                  >
                    <TriangleAlert data-icon="inline-start" />
                    {unavailableMembersLabel}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent side="bottom" align="start">
                  {unavailableMemberTooltip}
                </TooltipContent>
              </Tooltip>
            ) : null}
          </div>
          {group.is_route_group ? (
            <ItemDescription className="text-sm">
              {`${group.name} -> ${group.route_group_name || group.route_group_id || "n/a"}`}
            </ItemDescription>
          ) : (
            <CompactPriceSummary
              locale={locale}
              inputPrice={group.input_price_per_million}
              outputPrice={group.output_price_per_million}
              cacheReadPrice={group.cache_read_price_per_million}
              cacheWritePrice={group.cache_write_price_per_million}
            />
          )}
        </div>
        {!group.is_route_group ? (
          <ItemFooter
            className="mt-3 flex flex-wrap items-center gap-2.5"
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => event.stopPropagation()}
          >
            <StrategyToggle
              value={group.strategy}
              locale={locale}
              disabled={busyId === group.id}
              size="sm"
              className="w-fit max-w-full"
              onChange={(value) => void changeStrategy(group, value)}
            />
          </ItemFooter>
        ) : null}
        <div
          className="mt-3 flex flex-wrap items-center gap-2"
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          <ModelGroupMemberChips
            group={group}
            locale={locale}
            busyId={busyId}
            cardDragging={cardDragging}
            setCardDragging={setCardDragging}
            reorderGroupMembers={reorderGroupMembers}
            removeGroupMember={removeGroupMember}
            unavailableMemberStatusLabel={unavailableMemberStatusLabel}
            unavailableMemberTooltip={unavailableMemberTooltip}
          />
        </div>
      </ItemContent>
      <ItemActions
        className="basis-full flex-wrap justify-end self-start sm:ml-auto sm:basis-auto sm:shrink-0"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
      >
        <Switch
          checked={isGroupEnabled(group)}
          disabled={
            group.is_route_group || busyId === group.id || !group.items.length
          }
          onCheckedChange={(checked) => void toggleGroupEnabled(group, checked)}
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-destructive hover:text-destructive"
          onClick={() => setDeleteTarget(group)}
        >
          <Trash2 data-icon="inline-start" />
          {locale === "zh-CN" ? "删除" : "Delete"}
        </Button>
      </ItemActions>
    </Item>
  );
}
