import {
  AlertCircle,
  ChevronDown,
  Eraser,
  Plus,
  Power,
  PowerOff,
  Settings2,
  Trash2,
} from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import { Button } from "@/components/ui/Button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { FilterPillGroup } from "@/components/ui/FilterPillGroup";
import type { RoutingStrategy } from "@/lib/api/groups";
import type { MemberStatusFilter } from "./groupTypes";
import { ModelGroupSelectedMemberList } from "./ModelGroupSelectedMemberList";
import type { GroupMembers } from "./useGroupMembers";

interface ModelGroupSelectedMembersProps {
  onAddSources: () => void;
  locale: "zh-CN" | "en-US";
  strategy: RoutingStrategy;
  members: Omit<GroupMembers, "excludedMembers" | "restoreExcludedMember">;
  memberStatusFilter: MemberStatusFilter;
  setMemberStatusFilter: Dispatch<SetStateAction<MemberStatusFilter>>;
}

/** Render selected model controls and draggable member rows. */
export function ModelGroupSelectedMembers({
  onAddSources,
  locale,
  strategy,
  members,
  memberStatusFilter,
  setMemberStatusFilter,
}: ModelGroupSelectedMembersProps) {
  const {
    foldedMembers,
    disabledItemCount,
    invalidItemCount,
    removeInvalidItems,
    removeDisabledMembers,
    clearMembers,
    setAllMembersEnabled,
  } = members;
  const itemCount = foldedMembers.reduce(
    (count, member) => count + member.subItems.length,
    0,
  );
  const enabledItemCount = itemCount - disabledItemCount;

  return (
    <section
      className="flex shrink-0 flex-col gap-3 pt-2"
      aria-label={locale === "zh-CN" ? "渠道成员" : "Channel members"}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <h4 className="text-sm font-semibold text-card-foreground">
            {locale === "zh-CN" ? "渠道成员" : "Channel members"}
          </h4>
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {foldedMembers.length}
          </span>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 text-[13px]"
          onClick={onAddSources}
        >
          <Plus data-icon="inline-start" />
          {locale === "zh-CN" ? "添加成员" : "Add members"}
        </Button>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <FilterPillGroup
          value={memberStatusFilter}
          ariaLabel={locale === "zh-CN" ? "成员状态" : "Member status"}
          onValueChange={(value) =>
            setMemberStatusFilter(value as MemberStatusFilter)
          }
          options={[
            {
              value: "all",
              label: locale === "zh-CN" ? "全部" : "All",
            },
            {
              value: "enabled",
              label: locale === "zh-CN" ? "已启用" : "Enabled",
            },
            {
              value: "disabled",
              label: locale === "zh-CN" ? "已停用" : "Paused",
            },
            {
              value: "problem",
              label: locale === "zh-CN" ? "需处理" : "Issues",
            },
          ]}
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 px-2 text-[13px] font-normal text-muted-foreground hover:text-foreground"
              disabled={!foldedMembers.length}
            >
              <Settings2 data-icon="inline-start" />
              {locale === "zh-CN" ? "批量操作" : "Bulk actions"}
              <ChevronDown data-icon="inline-end" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuGroup>
              <DropdownMenuItem
                onSelect={() => setAllMembersEnabled(true)}
                disabled={disabledItemCount === 0}
              >
                <Power />
                {locale === "zh-CN" ? "全部启用" : "Enable all"}
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => setAllMembersEnabled(false)}
                disabled={enabledItemCount === 0}
              >
                <PowerOff />
                {locale === "zh-CN" ? "全部关闭" : "Disable all"}
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem
                onSelect={removeDisabledMembers}
                disabled={disabledItemCount === 0}
              >
                <Trash2 />
                {locale === "zh-CN"
                  ? `移除已关闭项 (${disabledItemCount})`
                  : `Remove disabled (${disabledItemCount})`}
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={removeInvalidItems}
                disabled={invalidItemCount === 0}
              >
                <AlertCircle />
                {locale === "zh-CN"
                  ? `移除配置错误 (${invalidItemCount})`
                  : `Remove invalid (${invalidItemCount})`}
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem onSelect={clearMembers}>
                <Eraser />
                {locale === "zh-CN"
                  ? `清空全部 (${foldedMembers.length})`
                  : `Clear all (${foldedMembers.length})`}
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="divide-y divide-border/50 border-t border-border/50">
        <ModelGroupSelectedMemberList
          locale={locale}
          strategy={strategy}
          memberStatusFilter={memberStatusFilter}
          {...members}
        />
      </div>
    </section>
  );
}
