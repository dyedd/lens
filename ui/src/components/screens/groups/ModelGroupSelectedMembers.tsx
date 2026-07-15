import type { Dispatch, SetStateAction } from "react";
import {
  AlertCircle,
  Ban,
  ChevronDown,
  Eraser,
  Power,
  PowerOff,
  Settings2,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/ToggleGroup";
import { FoldedMemberRow } from "./ModelGroupEditorFields";
import type { FoldedMember, MemberStatusFilter } from "./modelGroupUtils";

interface ModelGroupSelectedMembersProps {
  locale: "zh-CN" | "en-US";
  foldedMembers: FoldedMember[];
  disabledItemCount: number;
  invalidItemCount: number;
  unavailableItemCount: number;
  removeInvalidItems: () => void;
  removeUnavailableItems: () => void;
  removeDisabledMembers: () => void;
  clearMembers: () => void;
  setAllMembersEnabled: (enabled: boolean) => void;
  memberStatusFilter: MemberStatusFilter;
  setMemberStatusFilter: Dispatch<SetStateAction<MemberStatusFilter>>;
  visibleFoldedMembers: Array<{ member: FoldedMember; index: number }>;
  draggingIndex: number | null;
  toggleFoldedMember: (foldKey: string, enabled: boolean) => void;
  removeFoldedMember: (foldKey: string) => void;
  setDraggingIndex: Dispatch<SetStateAction<number | null>>;
  moveFoldedMember: (fromIndex: number, toIndex: number) => void;
}

/** Render selected model controls and draggable member rows. */
export function ModelGroupSelectedMembers({
  locale,
  foldedMembers,
  disabledItemCount,
  invalidItemCount,
  unavailableItemCount,
  removeInvalidItems,
  removeUnavailableItems,
  removeDisabledMembers,
  clearMembers,
  setAllMembersEnabled,
  memberStatusFilter,
  setMemberStatusFilter,
  visibleFoldedMembers,
  draggingIndex,
  toggleFoldedMember,
  removeFoldedMember,
  setDraggingIndex,
  moveFoldedMember,
}: ModelGroupSelectedMembersProps) {
  const itemCount = foldedMembers.reduce(
    (count, member) => count + member.subItems.length,
    0,
  );
  const enabledItemCount = itemCount - disabledItemCount;
  const emptyMessage =
    memberStatusFilter === "all"
      ? locale === "zh-CN"
        ? "暂无已选模型"
        : "No selected models"
      : memberStatusFilter === "enabled"
        ? locale === "zh-CN"
          ? "没有包含启用项的模型"
          : "No models with enabled items"
        : memberStatusFilter === "disabled"
          ? locale === "zh-CN"
            ? "没有包含关闭项的模型"
            : "No models with disabled items"
          : locale === "zh-CN"
            ? "没有异常模型"
            : "No problematic models";

  return (
    <section className="flex flex-col rounded-lg bg-muted/10">
      <div className="flex flex-col items-start justify-between gap-3 px-2 py-1 sm:flex-row sm:items-center">
        <div className="text-sm font-medium text-foreground">
          {locale === "zh-CN" ? "已选模型" : "Selected models"}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <ToggleGroup
            type="single"
            value={memberStatusFilter}
            onValueChange={(value) => {
              if (value) {
                setMemberStatusFilter(value as MemberStatusFilter);
              }
            }}
            variant="outline"
            size="sm"
            spacing={0}
            aria-label={
              locale === "zh-CN" ? "成员状态筛选" : "Member status filter"
            }
          >
            <ToggleGroupItem
              value="all"
              aria-label={locale === "zh-CN" ? "显示全部" : "Show all"}
            >
              {locale === "zh-CN" ? "全部" : "All"}
            </ToggleGroupItem>
            <ToggleGroupItem
              value="enabled"
              aria-label={locale === "zh-CN" ? "显示已启用" : "Show enabled"}
            >
              {locale === "zh-CN" ? "含启用" : "Has enabled"}
            </ToggleGroupItem>
            <ToggleGroupItem
              value="disabled"
              aria-label={locale === "zh-CN" ? "显示已关闭" : "Show disabled"}
            >
              {locale === "zh-CN" ? "含关闭" : "Has disabled"}
            </ToggleGroupItem>
            <ToggleGroupItem
              value="problem"
              aria-label={locale === "zh-CN" ? "显示异常" : "Show problems"}
            >
              {locale === "zh-CN" ? "异常" : "Problems"}
            </ToggleGroupItem>
          </ToggleGroup>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
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
                  variant="destructive"
                  onSelect={removeDisabledMembers}
                  disabled={disabledItemCount === 0}
                >
                  <Trash2 />
                  {locale === "zh-CN"
                    ? `移除已关闭项 (${disabledItemCount})`
                    : `Remove disabled (${disabledItemCount})`}
                </DropdownMenuItem>
                <DropdownMenuItem
                  variant="destructive"
                  onSelect={removeInvalidItems}
                  disabled={invalidItemCount === 0}
                >
                  <AlertCircle />
                  {locale === "zh-CN"
                    ? `移除配置错误 (${invalidItemCount})`
                    : `Remove invalid (${invalidItemCount})`}
                </DropdownMenuItem>
                <DropdownMenuItem
                  variant="destructive"
                  onSelect={removeUnavailableItems}
                  disabled={unavailableItemCount === 0}
                >
                  <Ban />
                  {locale === "zh-CN"
                    ? `移除当前不可用 (${unavailableItemCount})`
                    : `Remove unavailable (${unavailableItemCount})`}
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem variant="destructive" onSelect={clearMembers}>
                  <Eraser />
                  {locale === "zh-CN"
                    ? `清空全部 (${foldedMembers.length})`
                    : `Clear all (${foldedMembers.length})`}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
          <Badge variant="secondary">
            {visibleFoldedMembers.length}/{foldedMembers.length}
          </Badge>
        </div>
      </div>
      <div className="px-2 pb-2 pt-1">
        <div className="flex flex-col gap-1.5">
          {visibleFoldedMembers.length ? (
            visibleFoldedMembers.map(({ member, index }) => (
              <FoldedMemberRow
                key={member.key}
                member={member}
                index={index}
                isDragging={draggingIndex === index}
                isBusy={false}
                canReorder={memberStatusFilter === "all"}
                onToggle={() =>
                  toggleFoldedMember(
                    member.key,
                    member.enabled_item_count === 0,
                  )
                }
                onRemove={() => removeFoldedMember(member.key)}
                onDragStart={() => setDraggingIndex(index)}
                onDragEnter={() => {
                  if (draggingIndex === null || draggingIndex === index) return;
                  moveFoldedMember(draggingIndex, index);
                  setDraggingIndex(index);
                }}
                onDragEnd={() => setDraggingIndex(null)}
                locale={locale}
              />
            ))
          ) : (
            <p className="px-1 py-6 text-center text-sm text-muted-foreground">
              {emptyMessage}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
