import { AlertCircle, ChevronDown } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Separator } from "@/components/ui/Separator";
import type { ModelGroupCandidateItem, ProtocolKind } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CandidateRow } from "./ModelGroupEditorFields";
import { itemKey, type CandidateChannelGroup } from "./modelGroupUtils";

interface ModelGroupCandidateListProps {
  locale: "zh-CN" | "en-US";
  protocols: ProtocolKind[];
  groupedCandidates: CandidateChannelGroup[];
  expandedChannels: string[];
  existingItemKeys: Set<string>;
  toggleChannel: (channelId: string) => void;
  addCandidate: (candidate: ModelGroupCandidateItem) => void;
  sitesIsError: boolean;
  candidateIsError: boolean;
  candidateListError: unknown;
}

/** Render candidate models grouped by channel. */
export function ModelGroupCandidateList({
  locale,
  protocols,
  groupedCandidates,
  expandedChannels,
  existingItemKeys,
  toggleChannel,
  addCandidate,
  sitesIsError,
  candidateIsError,
  candidateListError,
}: ModelGroupCandidateListProps) {
  return (
    <div className="px-2 pb-2">
      <div className="flex flex-col">
        {groupedCandidates.map((channelGroup) => {
          const isOpen = expandedChannels.includes(channelGroup.key);
          return (
            <div key={channelGroup.key} className="border-b last:border-b-0">
              <Button
                type="button"
                variant="ghost"
                className="h-auto min-h-11 w-full justify-start gap-3 rounded-none px-3 py-2 text-left hover:bg-muted"
                onClick={() => toggleChannel(channelGroup.key)}
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-foreground">
                    {channelGroup.channel_name}
                  </div>
                </div>
                <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                  {channelGroup.candidates.length}
                </span>
                <ChevronDown
                  size={15}
                  className={cn(
                    "text-muted-foreground transition-transform",
                    isOpen && "rotate-180",
                  )}
                />
              </Button>
              {isOpen ? (
                <div className="flex flex-col gap-0.5 px-3 pb-2 pt-1">
                  <Separator className="mb-1" />
                  {channelGroup.candidates.map((candidate) => (
                    <CandidateRow
                      key={`${candidate.protocol_config_id}-${candidate.credential_id}-${candidate.model_name}`}
                      candidate={candidate}
                      active={candidate.items.every((item) =>
                        existingItemKeys.has(itemKey(item)),
                      )}
                      selectedProtocols={protocols}
                      locale={locale}
                      onClick={() => addCandidate(candidate)}
                    />
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
        {sitesIsError || candidateIsError ? (
          <Alert variant="destructive" className="my-2">
            <AlertCircle />
            <AlertTitle>
              {candidateIsError
                ? locale === "zh-CN"
                  ? "候选模型加载失败"
                  : "Failed to load candidates"
                : locale === "zh-CN"
                  ? "渠道加载失败"
                  : "Failed to load channels"}
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
          <p className="px-1 py-6 text-center text-sm text-muted-foreground">
            {protocols.length === 0
              ? locale === "zh-CN"
                ? "请先在上方选择对外协议以加载候选节点。"
                : "Select external protocols above to load candidates."
              : locale === "zh-CN"
                ? "暂无可选模型"
                : "No candidates found"}
          </p>
        ) : null}
      </div>
    </div>
  );
}
