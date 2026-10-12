import { X } from "lucide-react";
import { type KeyboardEvent, useState } from "react";
import { RegexRulePicker } from "@/components/ruleEditors/RegexRulePicker";
import { Badge } from "@/components/ui/Badge";
import type { RegexRule } from "@/lib/api/regexRules";

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
  onMatchModelsChange: (matchModels: string[]) => void;
  onMatchRuleIdsChange: (matchRuleIds: string[]) => void;
}

/** Edit the live match rules that pull channel models into a group. */
export function ModelGroupMatchRules({
  locale,
  matchModels,
  matchRuleIds,
  invalidMatchRules,
  hasDeletedMatchRules,
  ruleMatchModelCount,
  ruleMatchSourceCount,
  onMatchModelsChange,
  onMatchRuleIdsChange,
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
          ? "名称匹配的可用模型会自动加入这个模型组；新模型也会自动生效。"
          : "Available models whose names match are added automatically, including new models."}
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
