import { X } from "lucide-react";
import { type KeyboardEvent, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";

interface ModelGroupMatchRulesProps {
  locale: "zh-CN" | "en-US";
  matchModels: string[];
  matchRegex: string;
  matchRegexInvalid: boolean;
  ruleMatchModelCount: number;
  ruleMatchSourceCount: number;
  onMatchModelsChange: (matchModels: string[]) => void;
  onMatchRegexChange: (matchRegex: string) => void;
}

/** Edit the live match rules that pull channel models into a group. */
export function ModelGroupMatchRules({
  locale,
  matchModels,
  matchRegex,
  matchRegexInvalid,
  ruleMatchModelCount,
  ruleMatchSourceCount,
  onMatchModelsChange,
  onMatchRegexChange,
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
      aria-label={locale === "zh-CN" ? "自动匹配" : "Match rules"}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium">
          {locale === "zh-CN" ? "自动匹配" : "Match rules"}
        </h3>
        <span className="text-xs tabular-nums text-muted-foreground">
          {locale === "zh-CN"
            ? `匹配 ${ruleMatchModelCount} 个模型名 · ${ruleMatchSourceCount} 个来源`
            : `${ruleMatchModelCount} names · ${ruleMatchSourceCount} sources`}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        {locale === "zh-CN"
          ? "渠道中名称匹配（不区分大小写）的可用模型实时加入，新密钥和新站点同步后自动生效。"
          : "Available channel models whose names match (case-insensitive) join live, including new keys and sites."}
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
          aria-label={locale === "zh-CN" ? "匹配模型名" : "Match model name"}
          placeholder={
            locale === "zh-CN" ? "输入模型名后回车" : "Type a model name, Enter"
          }
          className="h-6 min-w-32 flex-1 bg-transparent font-mono text-xs outline-none placeholder:font-sans placeholder:text-muted-foreground"
        />
      </div>
      <Input
        value={matchRegex}
        onChange={(event) => onMatchRegexChange(event.target.value)}
        aria-invalid={matchRegexInvalid}
        aria-label={locale === "zh-CN" ? "匹配正则" : "Match regex"}
        placeholder={
          locale === "zh-CN"
            ? "正则（可选），如 ^claude-opus"
            : "Regex (optional), e.g. ^claude-opus"
        }
        className="font-mono"
      />
      {matchRegexInvalid ? (
        <p className="text-xs text-destructive">
          {locale === "zh-CN" ? "正则表达式无效" : "Invalid regex"}
        </p>
      ) : null}
    </section>
  );
}
