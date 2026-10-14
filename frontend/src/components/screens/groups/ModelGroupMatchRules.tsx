import { X } from "lucide-react";
import { type KeyboardEvent, useState } from "react";
import { RegexRulePicker } from "@/components/ruleEditors/RegexRulePicker";
import { Badge } from "@/components/ui/Badge";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import type { ModelGroupNewMemberPosition } from "@/lib/api/groups";
import type { RegexRule } from "@/lib/api/regexRules";
import { NEW_MEMBER_POSITION_OPTIONS } from "./modelGroupFormatting";

interface ModelGroupMatchRulesProps {
  locale: "zh-CN" | "en-US";
  matchModels: string[];
  matchRuleIds: string[];
  /** Attached rules whose pattern JS cannot compile; they block saving. */
  invalidMatchRules: RegexRule[];
  /** Attached ids missing from the library; they block saving. */
  hasDeletedMatchRules: boolean;
  ruleMatchModelCount: number;
  ruleMatchSourceCount: number;
  newMemberPosition: ModelGroupNewMemberPosition;
  /** Members saving adds or removes compared with the saved group. */
  memberChange: { added: number; removed: number } | null;
  onMatchModelsChange: (matchModels: string[]) => void;
  onMatchRuleIdsChange: (matchRuleIds: string[]) => void;
  onNewMemberPositionChange: (position: ModelGroupNewMemberPosition) => void;
}

/** Edit the match rules that pull channel models into a group. */
export function ModelGroupMatchRules({
  locale,
  matchModels,
  matchRuleIds,
  invalidMatchRules,
  hasDeletedMatchRules,
  ruleMatchModelCount,
  ruleMatchSourceCount,
  newMemberPosition,
  memberChange,
  onMatchModelsChange,
  onMatchRuleIdsChange,
  onNewMemberPositionChange,
}: ModelGroupMatchRulesProps) {
  const [draft, setDraft] = useState("");

  function addDraft() {
    const name = draft.trim();
    setDraft("");
    if (
      !name ||
      matchModels.some((item) => item.toLowerCase() === name.toLowerCase())
    ) {
      return;
    }
    onMatchModelsChange([...matchModels, name]);
  }

  function handleDraftKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.nativeEvent.isComposing) return;
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addDraft();
    } else if (event.key === "Backspace" && !draft && matchModels.length) {
      onMatchModelsChange(matchModels.slice(0, -1));
    }
  }

  return (
    <section
      className="flex shrink-0 flex-col gap-2"
      aria-label={locale === "zh-CN" ? "自动加入" : "Auto-add"}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium">
          {locale === "zh-CN" ? "自动加入" : "Auto-add"}
        </h3>
        <span className="text-xs tabular-nums text-muted-foreground">
          {locale === "zh-CN"
            ? `已加入 ${ruleMatchModelCount} 个模型名 · ${ruleMatchSourceCount} 个渠道`
            : `${ruleMatchModelCount} names · ${ruleMatchSourceCount} channels`}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        {locale === "zh-CN"
          ? "名称匹配的可用模型会在保存和每次同步时加入这个模型组，并保存为成员。"
          : "Available models whose names match join this group as saved members on save and on every sync."}
      </p>
      <div className="flex min-h-8 flex-wrap items-center gap-1 rounded-md border border-input/40 px-2 py-1 focus-within:border-primary/60 focus-within:ring-[1px] focus-within:ring-primary/40">
        {matchModels.map((name) => (
          <Badge
            key={name}
            variant="secondary"
            className="gap-0.5 pr-0.5 font-mono text-foreground"
          >
            {name}
            <button
              type="button"
              className="grid size-4 place-items-center rounded-full text-muted-foreground hover:bg-background hover:text-foreground"
              aria-label={
                locale === "zh-CN" ? `移除 ${name}` : `Remove ${name}`
              }
              onClick={() =>
                onMatchModelsChange(matchModels.filter((item) => item !== name))
              }
            >
              <X className="size-3" />
            </button>
          </Badge>
        ))}
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleDraftKeyDown}
          onBlur={addDraft}
          aria-label={
            locale === "zh-CN" ? "匹配模型名称" : "Model name to match"
          }
          placeholder={
            locale === "zh-CN"
              ? "输入模型名称后按 Enter"
              : "Type a model name and press Enter"
          }
          className="h-6 min-w-32 flex-1 bg-transparent font-mono text-xs outline-none placeholder:font-sans placeholder:text-muted-foreground"
        />
      </div>
      <div className="flex items-start gap-2">
        <span className="shrink-0 text-xs leading-6 text-muted-foreground">
          {locale === "zh-CN" ? "正则规则" : "Regex rules"}
        </span>
        <RegexRulePicker
          locale={locale}
          label={locale === "zh-CN" ? "匹配正则规则" : "Match regex rules"}
          value={matchRuleIds}
          onChange={onMatchRuleIdsChange}
        />
      </div>
      <div className="flex items-center gap-2">
        <span className="shrink-0 text-xs text-muted-foreground">
          {locale === "zh-CN" ? "新成员放在" : "New members go"}
        </span>
        <Select
          value={newMemberPosition}
          onValueChange={(value) =>
            onNewMemberPositionChange(value as ModelGroupNewMemberPosition)
          }
        >
          <SelectTrigger
            className="h-7 w-auto min-w-32"
            aria-label={
              locale === "zh-CN" ? "新成员位置" : "New member position"
            }
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {NEW_MEMBER_POSITION_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {locale === "zh-CN" ? option.zh : option.en}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>
      {memberChange && (memberChange.added || memberChange.removed) ? (
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {locale === "zh-CN"
            ? `保存后：新增 ${memberChange.added} 个成员，移除 ${memberChange.removed} 个成员`
            : `On save: ${memberChange.added} members added, ${memberChange.removed} removed`}
        </p>
      ) : null}
      {invalidMatchRules.length ? (
        <p className="text-xs text-destructive">
          {locale === "zh-CN"
            ? `规则正则无效：${invalidMatchRules.map((rule) => rule.name).join("、")}`
            : `Invalid rule regex: ${invalidMatchRules.map((rule) => rule.name).join(", ")}`}
        </p>
      ) : null}
      {hasDeletedMatchRules ? (
        <p className="text-xs text-destructive">
          {locale === "zh-CN"
            ? "移除已删除的规则后才能保存"
            : "Remove the deleted rules to save"}
        </p>
      ) : null}
    </section>
  );
}
