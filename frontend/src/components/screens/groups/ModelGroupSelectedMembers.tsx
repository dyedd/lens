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
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/Accordion";
import { Button } from "@/components/ui/Button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import type { RoutingStrategy } from "@/lib/api/groups";
import type {
  ChannelMemberGroup,
  FoldedMember,
  MemberStatusFilter,
} from "./groupTypes";
import { ModelGroupSelectedMemberList } from "./ModelGroupSelectedMemberList";

interface ModelGroupSelectedMembersProps {
  onAddSources: () => void;
  locale: "zh-CN" | "en-US";
  strategy: RoutingStrategy;
  foldedMembers: FoldedMember[];
  disabledItemCount: number;
  invalidItemCount: number;
  removeInvalidItems: () => void;
  removeDisabledMembers: () => void;
  clearMembers: () => void;
  setAllMembersEnabled: (enabled: boolean) => void;
  memberStatusFilter: MemberStatusFilter;
  setMemberStatusFilter: Dispatch<SetStateAction<MemberStatusFilter>>;
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

/** Render selected model controls and draggable member rows. */
export function ModelGroupSelectedMembers({
  onAddSources,
  locale,
  strategy,
  foldedMembers,
  disabledItemCount,
  invalidItemCount,
  removeInvalidItems,
  removeDisabledMembers,
  clearMembers,
  setAllMembersEnabled,
  memberStatusFilter,
  setMemberStatusFilter,
  visibleFoldedMembers,
  visibleChannelGroups,
  toggleChannelMembers,
  toggleFoldedMember,
  removeFoldedMember,
  moveChannelGroup,
  moveFoldedMember,
  moveFoldedMemberWithinChannel,
}: ModelGroupSelectedMembersProps) {
  const itemCount = foldedMembers.reduce(
    (count, member) => count + member.subItems.length,
    0,
  );
  const enabledItemCount = itemCount - disabledItemCount;

  return (
    <section
      className="flex shrink-0 flex-col"
      aria-label={locale === "zh-CN" ? "渠道成员" : "Channel members"}
    >
      <Accordion
        type="single"
        collapsible
        defaultValue="members"
        className="w-full"
      >
        <AccordionItem value="members" className="border-0">
          <AccordionTrigger className="items-center py-0 text-xs font-normal text-muted-foreground hover:no-underline">
            <span className="flex items-center gap-2">
              <span>{locale === "zh-CN" ? "渠道成员" : "Channel members"}</span>
              <span className="tabular-nums">{foldedMembers.length}</span>
            </span>
          </AccordionTrigger>
          <AccordionContent className="pt-3">
            <div className="flex min-w-0 flex-wrap items-center justify-end gap-2 rounded-md bg-muted/35 p-1.5">
              <div className="flex items-center gap-1">
                <Select
                  value={memberStatusFilter}
                  onValueChange={(value) =>
                    setMemberStatusFilter(value as MemberStatusFilter)
                  }
                >
                  <SelectTrigger
                    className="h-7 w-auto min-w-24"
                    aria-label={
                      locale === "zh-CN" ? "成员状态" : "Member status"
                    }
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="all">
                        {locale === "zh-CN" ? "全部状态" : "All statuses"}
                      </SelectItem>
                      <SelectItem value="enabled">
                        {locale === "zh-CN" ? "含启用" : "Has enabled"}
                      </SelectItem>
                      <SelectItem value="disabled">
                        {locale === "zh-CN" ? "含关闭" : "Has disabled"}
                      </SelectItem>
                      <SelectItem value="problem">
                        {locale === "zh-CN" ? "需处理" : "Needs attention"}
                      </SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
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
              <Button type="button" size="sm" onClick={onAddSources}>
                <Plus data-icon="inline-start" />
                {locale === "zh-CN" ? "添加成员" : "Add members"}
              </Button>
            </div>
            <div className="mt-3 overflow-hidden rounded-md bg-muted/35 p-1">
              <ModelGroupSelectedMemberList
                locale={locale}
                strategy={strategy}
                memberStatusFilter={memberStatusFilter}
                visibleFoldedMembers={visibleFoldedMembers}
                visibleChannelGroups={visibleChannelGroups}
                toggleChannelMembers={toggleChannelMembers}
                toggleFoldedMember={toggleFoldedMember}
                removeFoldedMember={removeFoldedMember}
                moveChannelGroup={moveChannelGroup}
                moveFoldedMember={moveFoldedMember}
                moveFoldedMemberWithinChannel={moveFoldedMemberWithinChannel}
              />
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </section>
  );
}
