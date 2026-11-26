import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { TruncatedTooltip } from "@/components/ui/Tooltip";
import type { FoldedMember } from "./groupTypes";
import { formatMemberIdentity } from "./modelGroupFormatting";

interface ModelGroupExcludedMembersProps {
  locale: "zh-CN" | "en-US";
  excludedMembers: FoldedMember[];
  restoreExcludedMember: (foldKey: string) => void;
}

/** List members kept out of the group so they can be brought back. */
export function ModelGroupExcludedMembers({
  locale,
  excludedMembers,
  restoreExcludedMember,
}: ModelGroupExcludedMembersProps) {
  if (!excludedMembers.length) return null;
  const isZh = locale === "zh-CN";

  return (
    <section
      className="flex shrink-0 flex-col gap-2.5"
      aria-label={isZh ? "已排除" : "Excluded"}
    >
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-semibold text-card-foreground">
          {isZh ? "未满足条件的成员" : "Filtered-out members"}
        </h4>
        <span className="inline-flex h-5 items-center rounded-full bg-muted px-2 font-mono text-xs font-medium tabular-nums text-muted-foreground">
          {excludedMembers.length}
        </span>
      </div>
      <ul className="flex flex-col divide-y divide-border/50">
        {excludedMembers.map((member) => {
          const identity = formatMemberIdentity(member.subItems, locale);
          return (
            <li
              key={member.key}
              className="group/item flex min-w-0 items-center gap-2 px-1 py-2"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate font-mono text-[13px] text-foreground">
                  {member.model_name}
                </div>
                <TruncatedTooltip
                  content={identity}
                  contentClassName="max-w-sm break-all"
                >
                  <div className="truncate text-xs text-muted-foreground">
                    {identity}
                  </div>
                </TruncatedTooltip>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="intent-reveal"
                onClick={() => restoreExcludedMember(member.key)}
              >
                <RotateCcw data-icon="inline-start" />
                {isZh ? "恢复" : "Restore"}
              </Button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
