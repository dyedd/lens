import { RefreshCcw, Search, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import type { CandidateSearchMode, FormState } from "./modelGroupUtils";

interface ModelGroupCandidateToolbarProps {
  locale: "zh-CN" | "en-US";
  form: FormState;
  candidateSearchMode: CandidateSearchMode;
  changeCandidateSearchMode: (mode: CandidateSearchMode) => void;
  candidateSearch: string;
  changeCandidateSearch: (value: string) => void;
  addMatchedItems: () => void;
  candidateRegexInvalid: boolean;
  filteredCandidateCount: number;
  refetchCandidates: () => unknown;
  isFetchingCandidates: boolean;
  applySavedFilter: () => void;
  clearSavedFilter: () => void;
}

/** Render candidate search, refresh, and saved-filter actions. */
export function ModelGroupCandidateToolbar({
  locale,
  form,
  candidateSearchMode,
  changeCandidateSearchMode,
  candidateSearch,
  changeCandidateSearch,
  addMatchedItems,
  candidateRegexInvalid,
  filteredCandidateCount,
  refetchCandidates,
  isFetchingCandidates,
  applySavedFilter,
  clearSavedFilter,
}: ModelGroupCandidateToolbarProps) {
  return (
    <>
      <div className="grid gap-3 py-1 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <div className="grid min-w-0 gap-2 sm:grid-cols-[128px_minmax(0,1fr)]">
          <Select
            value={candidateSearchMode}
            onValueChange={(value) =>
              changeCandidateSearchMode(value as CandidateSearchMode)
            }
          >
            <SelectTrigger className="h-7 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="contains">
                {locale === "zh-CN" ? "包含" : "Contains"}
              </SelectItem>
              <SelectItem value="regex">
                {locale === "zh-CN" ? "正则" : "Regex"}
              </SelectItem>
            </SelectContent>
          </Select>
          <div className="flex min-w-0 items-center gap-2 rounded-md border bg-background px-3">
            <Search size={14} className="text-muted-foreground" />
            <Input
              className="min-w-0 flex-1 border-0 bg-transparent px-0 py-0 text-sm shadow-none focus-visible:ring-0"
              value={candidateSearch}
              onChange={(event) => changeCandidateSearch(event.target.value)}
              placeholder={
                candidateSearchMode === "regex"
                  ? locale === "zh-CN"
                    ? "输入正则表达式"
                    : "Enter regular expression"
                  : locale === "zh-CN"
                    ? "输入包含条件"
                    : "Enter contains filter"
              }
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={addMatchedItems}
            disabled={
              form.protocols.length === 0 ||
              candidateRegexInvalid ||
              (!filteredCandidateCount && !candidateSearch.trim())
            }
          >
            <Sparkles size={13} />
            {candidateSearch.trim()
              ? locale === "zh-CN"
                ? `加入并保存筛选 ${filteredCandidateCount}`
                : `Add and save filter ${filteredCandidateCount}`
              : locale === "zh-CN"
                ? `加入全部 ${filteredCandidateCount}`
                : `Add all ${filteredCandidateCount}`}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => void refetchCandidates()}
            disabled={isFetchingCandidates || form.protocols.length === 0}
          >
            <RefreshCcw size={13} />
            {locale === "zh-CN" ? "刷新列表" : "Refresh"}
          </Button>
        </div>
      </div>
      {candidateRegexInvalid ? (
        <div className="px-2 text-sm text-destructive">
          {locale === "zh-CN" ? "正则表达式无效" : "Invalid regex"}
        </div>
      ) : null}
      {form.sync_filter_mode && form.sync_filter_query ? (
        <div className="mx-2 mb-2 flex flex-col gap-2 rounded-md border bg-muted/20 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 text-sm text-muted-foreground">
            <span className="text-foreground">
              {locale === "zh-CN" ? "已保存筛选" : "Saved filter"}
            </span>
            <span className="mx-2">·</span>
            <span>
              {form.sync_filter_mode === "regex"
                ? locale === "zh-CN"
                  ? "正则"
                  : "Regex"
                : locale === "zh-CN"
                  ? "包含"
                  : "Contains"}
            </span>
            <span className="mx-2">·</span>
            <span className="break-all">{form.sync_filter_query}</span>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void applySavedFilter()}
            >
              <RefreshCcw data-icon="inline-start" />
              {locale === "zh-CN" ? "按规则更新" : "Update by rule"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="text-muted-foreground"
              onClick={clearSavedFilter}
            >
              <X data-icon="inline-start" />
              {locale === "zh-CN" ? "清除规则" : "Clear rule"}
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}
