import { RefreshCcw, Regex } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";

interface ModelGroupCandidateToolbarProps {
  locale: "zh-CN" | "en-US";
  candidateSearch: string;
  changeCandidateSearch: (value: string) => void;
  refetchCandidates: () => unknown;
  isFetchingCandidates: boolean;
  /** Treat the search text as a regex when true. */
  candidateRegex: boolean;
  onCandidateRegexChange: (value: boolean) => void;
  /** Adds every candidate the current search shows. */
  onAddAllCandidates: () => void;
  visibleCandidateCount: number;
}

/** Render candidate search and refresh actions. */
export function ModelGroupCandidateToolbar({
  locale,
  candidateSearch,
  changeCandidateSearch,
  refetchCandidates,
  isFetchingCandidates,
  candidateRegex,
  onCandidateRegexChange,
  onAddAllCandidates,
  visibleCandidateCount,
}: ModelGroupCandidateToolbarProps) {
  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-border/60 p-3">
      <ToolbarSearchInput
        className="max-w-none"
        value={candidateSearch}
        onChange={changeCandidateSearch}
        onClear={() => changeCandidateSearch("")}
        placeholder={locale === "zh-CN" ? "搜索模型名称" : "Search models"}
      />
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant={candidateRegex ? "secondary" : "ghost"}
            size="icon-sm"
            aria-pressed={candidateRegex}
            aria-label={locale === "zh-CN" ? "正则搜索" : "Regex search"}
            onClick={() => onCandidateRegexChange(!candidateRegex)}
          >
            <Regex />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {locale === "zh-CN"
            ? "按正则匹配模型名"
            : "Match model names by regex"}
        </TooltipContent>
      </Tooltip>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-8 shrink-0"
        disabled={visibleCandidateCount === 0}
        onClick={onAddAllCandidates}
      >
        {locale === "zh-CN"
          ? `全部加入 (${visibleCandidateCount})`
          : `Add all (${visibleCandidateCount})`}
      </Button>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={locale === "zh-CN" ? "刷新列表" : "Refresh list"}
            onClick={() => void refetchCandidates()}
            disabled={isFetchingCandidates}
          >
            <RefreshCcw />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {locale === "zh-CN" ? "刷新列表" : "Refresh list"}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
