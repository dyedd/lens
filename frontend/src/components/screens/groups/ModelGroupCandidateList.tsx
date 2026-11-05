import { AlertCircle, ChevronDown } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import type { ModelGroupCandidateItem } from "@/lib/api/groups";
import { cn } from "@/lib/classNames";
import type { CandidateChannelGroup } from "./groupTypes";
import { CandidateRow } from "./ModelGroupMembers";
import { modelGroupItemKey } from "./modelGroupFormatting";

interface ModelGroupCandidateListProps {
  locale: "zh-CN" | "en-US";
  groupedCandidates: CandidateChannelGroup[];
  expandedChannels: string[];
  existingItemKeys: Set<string>;
  toggleChannel: (channelId: string) => void;
  addCandidate: (candidate: ModelGroupCandidateItem) => void;
  candidateIsError: boolean;
  candidateListError: unknown;
}

/** Render candidate models grouped by channel. */
export function ModelGroupCandidateList({
  locale,
  groupedCandidates,
  expandedChannels,
  existingItemKeys,
  toggleChannel,
  addCandidate,
  candidateIsError,
  candidateListError,
}: ModelGroupCandidateListProps) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
      <div className="flex flex-col">
        {groupedCandidates.map((channelGroup) => {
          const isOpen = expandedChannels.includes(channelGroup.key);
          const models = new Map<string, ModelGroupCandidateItem[]>();
          for (const candidate of channelGroup.candidates) {
            const candidates = models.get(candidate.model_name) ?? [];
            candidates.push(candidate);
            models.set(candidate.model_name, candidates);
          }
          return (
            <div key={channelGroup.key} className="py-0.5">
              <Button
                type="button"
                variant="ghost"
                className="h-auto min-h-8 w-full justify-start gap-2 rounded-md bg-muted/35 px-2 py-1 text-left hover:bg-muted/50"
                aria-expanded={isOpen}
                onClick={() => toggleChannel(channelGroup.key)}
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-medium text-foreground">
                    {channelGroup.channel_name}
                  </div>
                </div>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {models.size}
                </span>
                <ChevronDown
                  className={cn(
                    "size-3.5 text-muted-foreground transition-transform",
                    isOpen && "rotate-180",
                  )}
                />
              </Button>
              {isOpen ? (
                <div className="flex flex-col gap-0.5 pt-0.5 pl-1">
                  {Array.from(models, ([modelName, candidates]) => (
                    <CandidateRow
                      key={modelName}
                      candidates={candidates}
                      active={candidates.every((candidate) =>
                        candidate.items.every((item) =>
                          existingItemKeys.has(modelGroupItemKey(item)),
                        ),
                      )}
                      locale={locale}
                      onClick={() => candidates.forEach(addCandidate)}
                    />
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
        {candidateIsError ? (
          <Alert variant="destructive" className="my-2">
            <AlertCircle />
            <AlertTitle>
              {locale === "zh-CN"
                ? "候选模型加载失败"
                : "Failed to load candidates"}
            </AlertTitle>
            <AlertDescription>
              {candidateListError instanceof Error
                ? candidateListError.message
                : locale === "zh-CN"
                  ? "无法读取候选模型"
                  : "Unable to read candidates"}
            </AlertDescription>
          </Alert>
        ) : !groupedCandidates.length ? (
          <p className="px-1 py-6 text-center text-xs text-muted-foreground">
            {locale === "zh-CN" ? "暂无可选模型" : "No candidates found"}
          </p>
        ) : null}
      </div>
    </div>
  );
}
