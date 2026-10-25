import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { FoldedMember } from "./groupTypes";
import { formatCredentialIdentity } from "./modelGroupFormatting";

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
      className="flex shrink-0 flex-col gap-2 border-t border-border/60 pt-4"
      aria-label={isZh ? "已排除" : "Excluded"}
    >
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">
          {isZh ? "已排除" : "Excluded"}
        </h3>
        <span className="text-xs tabular-nums text-muted-foreground">
          {excludedMembers.length}
        </span>
      </div>
      <ul className="flex flex-col rounded-md bg-muted/35 p-1">
        {excludedMembers.map((member) => {
          const identity = formatCredentialIdentity(member, locale);
          return (
            <li
              key={member.key}
              className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate font-mono text-xs text-foreground">
                  {member.model_name}
                </div>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="truncate text-xs text-muted-foreground">
                      {identity}
                    </div>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-sm break-all">
                    {identity}
                  </TooltipContent>
                </Tooltip>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
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
