import type { Dispatch, SetStateAction } from "react";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { FoldedMemberRow } from "./ModelGroupEditorFields";
import type { FoldedMember } from "./modelGroupUtils";

interface ModelGroupSelectedMembersProps {
  locale: "zh-CN" | "en-US";
  foldedMembers: FoldedMember[];
  invalidSelectedMemberCount: number;
  removeInvalidItems: () => void;
  setAllMembersEnabled: (enabled: boolean) => void;
  showEnabledOnly: boolean;
  setShowEnabledOnly: Dispatch<SetStateAction<boolean>>;
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
  invalidSelectedMemberCount,
  removeInvalidItems,
  setAllMembersEnabled,
  showEnabledOnly,
  setShowEnabledOnly,
  visibleFoldedMembers,
  draggingIndex,
  toggleFoldedMember,
  removeFoldedMember,
  setDraggingIndex,
  moveFoldedMember,
}: ModelGroupSelectedMembersProps) {
  return (
    <section className="flex flex-col rounded-lg bg-muted/10">
      <div className="flex flex-col items-start justify-between gap-3 px-2 py-1 sm:flex-row sm:items-center">
        <div className="text-sm font-medium text-foreground">
          {locale === "zh-CN" ? "已选模型" : "Selected models"}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {invalidSelectedMemberCount > 0 ? (
            <Button
              type="button"
              variant="outline"
              className="text-destructive"
              onClick={removeInvalidItems}
            >
              <AlertCircle size={13} />
              {locale === "zh-CN" ? "一键移除失效节点" : "Remove invalid items"}
            </Button>
          ) : null}
          <Button
            type="button"
            variant="outline"
            className="text-muted-foreground"
            onClick={() => setAllMembersEnabled(true)}
          >
            {locale === "zh-CN" ? "全开" : "Enable all"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="text-muted-foreground"
            onClick={() => setAllMembersEnabled(false)}
          >
            {locale === "zh-CN" ? "全关" : "Disable all"}
          </Button>
          <Button
            type="button"
            variant={showEnabledOnly ? "default" : "outline"}
            className={cn(!showEnabledOnly && "text-muted-foreground")}
            onClick={() => setShowEnabledOnly((current) => !current)}
          >
            {locale === "zh-CN" ? "仅看启用" : "Enabled only"}
          </Button>
          <span className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
            {visibleFoldedMembers.length}/{foldedMembers.length}
          </span>
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
                onToggle={() => toggleFoldedMember(member.key, !member.enabled)}
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
              {locale === "zh-CN"
                ? "当前筛选下没有成员"
                : "No members under current filter"}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
