import { RefreshCcw, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import type { CandidateSearchMode, FormState } from "./groupTypes";

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
  clearSavedFilter,
}: ModelGroupCandidateToolbarProps) {
  return (
    <>
      <div className="flex shrink-0 flex-col gap-2 border-b p-3">
        <div className="grid min-w-0 gap-2 grid-cols-[88px_minmax(0,1fr)]">
          <Select
            value={candidateSearchMode}
            onValueChange={(value) =>
              changeCandidateSearchMode(value as CandidateSearchMode)
            }
          >
            <SelectTrigger
              className="w-full"
              aria-label={locale === "zh-CN" ? "筛选方式" : "Filter mode"}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="contains">
                  {locale === "zh-CN" ? "包含" : "Contains"}
                </SelectItem>
                <SelectItem value="exact">
                  {locale === "zh-CN" ? "等于" : "Equals"}
                </SelectItem>
                <SelectItem value="regex">
                  {locale === "zh-CN" ? "正则" : "Regex"}
                </SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          <ToolbarSearchInput
            className="max-w-none"
            value={candidateSearch}
            onChange={changeCandidateSearch}
            onClear={() => changeCandidateSearch("")}
            placeholder={
              candidateSearchMode === "regex"
                ? locale === "zh-CN"
                  ? "输入正则表达式"
                  : "Regular expression"
                : candidateSearchMode === "exact"
                  ? locale === "zh-CN"
                    ? "输入完整模型名称"
                    : "Exact model name"
                  : locale === "zh-CN"
                    ? "搜索模型名称"
                    : "Search models"
            }
          />
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addMatchedItems}
            disabled={
              candidateRegexInvalid ||
              (!filteredCandidateCount && !candidateSearch.trim())
            }
          >
            <Sparkles data-icon="inline-start" />
            {candidateSearch.trim()
              ? locale === "zh-CN"
                ? `设为自动包含规则 ${filteredCandidateCount}`
                : `Use as live rule ${filteredCandidateCount}`
              : locale === "zh-CN"
                ? `加入全部 ${filteredCandidateCount}`
                : `Add all ${filteredCandidateCount}`}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            aria-label={locale === "zh-CN" ? "刷新列表" : "Refresh list"}
            title={locale === "zh-CN" ? "刷新列表" : "Refresh list"}
            onClick={() => void refetchCandidates()}
            disabled={isFetchingCandidates}
          >
            <RefreshCcw />
          </Button>
        </div>
      </div>
      {candidateRegexInvalid ? (
        <div className="px-3 py-2 text-xs text-destructive">
          {locale === "zh-CN" ? "正则表达式无效" : "Invalid regex"}
        </div>
      ) : null}
      {form.sync_filter_mode && form.sync_filter_query ? (
        <div className="flex shrink-0 flex-col gap-2 border-b bg-muted/35 px-3 py-2">
          <div className="min-w-0 text-sm text-muted-foreground">
            <span className="text-foreground">
              {locale === "zh-CN" ? "自动包含（实时）" : "Live rule"}
            </span>
            <span className="mx-2">·</span>
            <span>
              {form.sync_filter_mode === "regex"
                ? locale === "zh-CN"
                  ? "正则"
                  : "Regex"
                : form.sync_filter_mode === "exact"
                  ? locale === "zh-CN"
                    ? "等于"
                    : "Equals"
                  : locale === "zh-CN"
                    ? "包含"
                    : "Contains"}
            </span>
            <span className="mx-2">·</span>
            <span className="break-all">{form.sync_filter_query}</span>
            <div className="mt-0.5 text-xs">
              {locale === "zh-CN"
                ? "所有渠道中名称匹配的可用模型会自动成为成员，新渠道或新同步的模型也会立即加入。"
                : "Every available channel model whose name matches joins automatically, including models from new channels and syncs."}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="destructive"
              size="sm"
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
