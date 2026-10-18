import type { Dispatch, ReactNode, SetStateAction } from "react";
import { RegexRulePicker } from "@/components/ruleEditors/RegexRulePicker";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { useRegexRules } from "@/hooks/useRegexRules";
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

/**
 * One editor row: a quiet label column beside its control.
 *
 * The label stacks above the control below `sm`, where the sheet is narrow.
 */
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
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-3">
      <Label
        htmlFor={htmlFor}
        required={required}
        className="text-xs font-normal text-muted-foreground sm:w-[72px] sm:shrink-0 sm:pt-2"
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
  const joinRules = useRegexRules();
  const joinPatterns = form.match_rule_ids.flatMap((ruleId) => {
    const rule = joinRules.rules.find((item) => item.id === ruleId);
    const pattern = rule ? compileRegexRulePattern(rule.pattern) : null;
    return pattern ? [pattern] : [];
  });
  const isJoinNameMismatched =
    joinPatterns.length > 0 &&
    form.name.trim() !== "" &&
    !joinPatterns.some((pattern) => pattern.test(form.name));

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

      <SettingsRow label={isZh ? "模型组类型" : "Group type"}>
        <SegmentedControl
          value={groupMode}
          onValueChange={handleModeChange}
          options={[
            {
              value: "direct",
              label: isZh ? "直接调度" : "Direct execution",
            },
            { value: "alias", label: isZh ? "别名" : "Alias" },
          ]}
        />
      </SettingsRow>

      <div className="flex flex-col gap-3 border-t border-border/60 pt-3">
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

            <SettingsRow
              htmlFor="group-context-window"
              label={isZh ? "默认上下文" : "Default context"}
            >
              <Input
                id="group-context-window"
                className="font-mono placeholder:font-sans"
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
              <p className="text-xs text-muted-foreground">
                {isContextWindowInvalid
                  ? isZh
                    ? "格式无效，示例：200K、1M、128000"
                    : "Invalid format. Examples: 200K, 1M, 128000"
                  : isZh
                    ? "仅用于没单独设置上下文的成员。请求估算超出某个成员的上下文时跳过它，改用上下文更大的成员；成员都没设置则不按上下文过滤。"
                    : "Only covers members without their own context window. A request estimated past a member's window skips it for a larger one; with nothing configured, routing ignores context."}
              </p>
            </SettingsRow>

            <SettingsRow label={isZh ? "匹配规则" : "Match rules"}>
              <div className="flex min-h-8 flex-wrap items-center gap-2">
                {form.match_rule_ids.length ? null : (
                  <span className="text-xs text-muted-foreground">
                    {isZh ? "按名称匹配" : "Matches by name"}
                  </span>
                )}
                <RegexRulePicker
                  label={isZh ? "匹配规则" : "Match rules"}
                  locale={locale}
                  value={form.match_rule_ids}
                  onChange={(ruleIds) =>
                    setForm((current) => ({
                      ...current,
                      match_rule_ids: ruleIds,
                    }))
                  }
                />
                {form.match_rule_ids.length ? (
                  <span className="min-w-0 flex-1 text-xs text-muted-foreground">
                    {isZh
                      ? "覆盖同名匹配，只加入匹配规则的模型。"
                      : "Replaces name matching; only matching models join."}
                  </span>
                ) : null}
              </div>
              {isJoinNameMismatched ? (
                <p className="text-xs text-muted-foreground">
                  {isZh
                    ? `名称「${form.name}」不匹配所选规则，它自己的同名模型不会自动加入。`
                    : `The name "${form.name}" matches no selected rule, so same-named models do not join.`}
                </p>
              ) : null}
            </SettingsRow>
          </>
        )}
      </div>
    </div>
  );
}
