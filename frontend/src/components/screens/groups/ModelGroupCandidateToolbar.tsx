import { RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";

interface ModelGroupCandidateToolbarProps {
  locale: "zh-CN" | "en-US";
  candidateSearch: string;
  changeCandidateSearch: (value: string) => void;
  refetchCandidates: () => unknown;
  isFetchingCandidates: boolean;
}

/** Render candidate search and refresh actions. */
export function ModelGroupCandidateToolbar({
  locale,
  candidateSearch,
  changeCandidateSearch,
  refetchCandidates,
  isFetchingCandidates,
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
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={locale === "zh-CN" ? "刷新列表" : "Refresh list"}
        title={locale === "zh-CN" ? "刷新列表" : "Refresh list"}
        onClick={() => void refetchCandidates()}
        disabled={isFetchingCandidates}
      >
        <RefreshCcw />
      </Button>
    </div>
  );
}
