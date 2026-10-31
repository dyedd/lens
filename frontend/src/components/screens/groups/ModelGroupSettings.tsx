import { ChevronUp, CircleHelp } from "lucide-react";
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useEffect,
  useState,
} from "react";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import type { ModelGroup } from "@/lib/api/groups";
import { parseContextWindowInput } from "@/lib/contextWindow";
import { compileRegexRulePattern } from "@/lib/regexRules";

import type { FormState } from "./groupTypes";

interface ModelGroupSettingsProps {
  locale: "zh-CN" | "en-US";
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  changeName: (name: string) => void;
  routeTargetOptions: ModelGroup[];
  changeRouteTarget: (routeGroupId: string) => void;
}

/** 标签始终位于控件上方，保持设置表单的纵向层级。 */
function SettingsRow({
  children,
  htmlFor,
  label,
  required = false,
}: {
  children: ReactNode;
  htmlFor?: string;
  label: string;
  required?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label
        htmlFor={htmlFor}
        required={required}
        className="text-xs leading-5 font-normal text-muted-foreground"
      >
        {label}
      </Label>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">{children}</div>
    </div>
  );
}

export function ModelGroupSettings({
  locale,
  form,
  setForm,
  changeName,
  routeTargetOptions,
  changeRouteTarget,
}: ModelGroupSettingsProps) {
  const isZh = locale === "zh-CN";
  const groupMode = form.route_group_id ? "alias" : "direct";
  const isContextWindowInvalid =
    parseContextWindowInput(form.context_window) === undefined;
  const [contextWindowMode, setContextWindowMode] = useState<"auto" | "custom">(
    form.context_window.trim() ? "custom" : "auto",
  );
  useEffect(() => {
    setContextWindowMode(form.context_window.trim() ? "custom" : "auto");
  }, [form.context_window]);
  const matchRegex = form.match_regex.trim();
  const isMatchRegexInvalid =
    Boolean(matchRegex) && !compileRegexRulePattern(matchRegex);

  function handleModeChange(mode: "direct" | "alias") {
    if (mode === "direct") {
      changeRouteTarget("");
    } else {
      const firstTarget = routeTargetOptions[0]?.id ?? "";
      changeRouteTarget(firstTarget);
    }
  }

  return (
    <div className="flex shrink-0 flex-col gap-3">
      <SettingsRow
        htmlFor="group-name"
        label={isZh ? "模型组名称" : "Group name"}
        required
      >
        <Input
          id="group-name"
          required
          className="font-mono placeholder:font-sans"
          placeholder={
            isZh
              ? "输入对外模型名，如 gpt-4o"
              : "Public model name, e.g. gpt-4o"
          }
          value={form.name}
          onChange={(event) => changeName(event.target.value)}
        />
      </SettingsRow>

      <SettingsRow
        htmlFor="group-type"
        label={isZh ? "模型组类型" : "Group type"}
      >
        <Select
          value={groupMode}
          onValueChange={(value) => {
            if (value === "direct" || value === "alias") {
              handleModeChange(value);
            }
          }}
        >
          <SelectTrigger id="group-type" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="direct">
                {isZh ? "直接调度" : "Direct execution"}
              </SelectItem>
              <SelectItem value="alias">{isZh ? "别名" : "Alias"}</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      </SettingsRow>

      <div className="flex flex-col gap-3">
        {groupMode === "alias" ? (
          <SettingsRow
            htmlFor="group-route-target"
            label={isZh ? "目标模型组" : "Target model group"}
            required
          >
            <Combobox
              id="group-route-target"
              className="w-full"
              value={form.route_group_id}
              onChange={(event) => changeRouteTarget(event.target.value)}
            >
              {routeTargetOptions.map((group) => (
                <ComboboxOption key={group.id} value={group.id}>
                  {group.name}
                </ComboboxOption>
              ))}
            </Combobox>
          </SettingsRow>
        ) : (
          <>
            <SettingsRow
              htmlFor="group-strategy"
              label={isZh ? "分发策略" : "Routing strategy"}
            >
              <Select
                value={form.strategy}
                onValueChange={(value) => {
                  if (value === "failover" || value === "round_robin")
                    setForm((current) => ({ ...current, strategy: value }));
                }}
              >
                <SelectTrigger id="group-strategy" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="failover">
                      {isZh ? "故障切换 (Failover)" : "Failover"}
                    </SelectItem>
                    <SelectItem value="round_robin">
                      {isZh ? "平滑轮询 (Round robin)" : "Round robin"}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </SettingsRow>

            <section className="flex flex-col gap-1.5 border-t border-border/60 pt-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-foreground">
                  {isZh ? "模型能力" : "Model capabilities"}
                </h3>
                <ChevronUp
                  aria-hidden="true"
                  className="size-3.5 text-muted-foreground"
                />
              </div>
              <p className="text-xs leading-5 text-muted-foreground">
                {isZh
                  ? "定义当前模型的上下文上限。"
                  : "Define the context limit for this model."}
              </p>
              <div className="flex min-h-10 items-center gap-1.5 rounded-md bg-muted/35 px-2 py-1.5">
                <div className="flex min-w-0 flex-1 items-center gap-1.5">
                  <label
                    htmlFor="group-context-window"
                    className="truncate text-xs font-medium text-foreground"
                  >
                    {isZh ? "上下文窗口" : "Context window"}
                  </label>
                  <CircleHelp
                    aria-hidden="true"
                    className="size-3 shrink-0 text-muted-foreground"
                  />
                </div>
                <Input
                  id="group-context-window"
                  className="h-8 min-w-0 flex-1 border-0 bg-transparent px-2 text-right font-mono text-xs shadow-none placeholder:font-sans focus-visible:border-0 focus-visible:ring-0"
                  inputMode="numeric"
                  aria-invalid={isContextWindowInvalid || undefined}
                  placeholder={isZh ? "如 200K、1M" : "e.g. 200K, 1M"}
                  value={form.context_window}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      context_window: event.target.value,
                    }))
                  }
                />
                <Select
                  value={contextWindowMode}
                  onValueChange={(value) => {
                    if (value === "auto") {
                      setContextWindowMode("auto");
                      setForm((current) => ({
                        ...current,
                        context_window: "",
                      }));
                    } else if (value === "custom") {
                      setContextWindowMode("custom");
                    }
                  }}
                >
                  <SelectTrigger className="h-8 w-[104px] shrink-0 border-0 bg-transparent px-2 text-xs shadow-none hover:bg-transparent focus-visible:border-0 focus-visible:ring-0">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="auto">
                        {isZh ? "自动识别" : "Detect automatically"}
                      </SelectItem>
                      <SelectItem value="custom">
                        {isZh ? "自定义" : "Custom"}
                      </SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
              <p
                className={
                  isContextWindowInvalid
                    ? "text-xs text-destructive"
                    : "text-xs text-muted-foreground"
                }
              >
                {isContextWindowInvalid
                  ? isZh
                    ? "格式无效，示例：200K、1M、128000"
                    : "Invalid format. Examples: 200K, 1M, 128000"
                  : isZh
                    ? "自定义值仅用于未单独设置上下文的成员；自动识别时使用成员窗口。"
                    : "Custom values apply to members without their own window; automatic mode uses each member's window."}
              </p>
            </section>

            <SettingsRow
              htmlFor="group-match-regex"
              label={isZh ? "匹配规则" : "Match rules"}
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="shrink-0 text-xs text-muted-foreground">
                  {isZh ? "名称包含" : "Name contains"}
                </span>
                <Select
                  value={form.match_regex_operator}
                  onValueChange={(value) => {
                    if (value === "and" || value === "or") {
                      setForm((current) => ({
                        ...current,
                        match_regex_operator: value,
                      }));
                    }
                  }}
                >
                  <SelectTrigger className="w-20 shrink-0">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="or">{isZh ? "或" : "OR"}</SelectItem>
                      <SelectItem value="and">{isZh ? "与" : "AND"}</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <Input
                  id="group-match-regex"
                  className="min-w-0 flex-1 font-mono placeholder:font-sans"
                  aria-invalid={isMatchRegexInvalid || undefined}
                  placeholder={
                    isZh
                      ? "可选正则，如 ^claude-"
                      : "Optional regex, e.g. ^claude-"
                  }
                  value={form.match_regex}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      match_regex: event.target.value,
                    }))
                  }
                />
              </div>
              <p
                className={
                  isMatchRegexInvalid
                    ? "text-xs text-destructive"
                    : "text-xs text-muted-foreground"
                }
              >
                {isMatchRegexInvalid
                  ? isZh
                    ? "正则表达式无效"
                    : "Invalid regex"
                  : isZh
                    ? "名称按不区分大小写的包含匹配；填写正则后按上面的与/或组合。"
                    : "The name matches case-insensitively by containment; combine an optional regex with AND/OR."}
              </p>
            </SettingsRow>
          </>
        )}
      </div>
    </div>
  );
}
