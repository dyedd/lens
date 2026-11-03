import type { Dispatch, ReactNode, SetStateAction } from "react";
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
import { buildPluginStrategyIds } from "./modelGroupFormatting";
import { usePluginStrategyIds } from "./usePluginStrategyIds";

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
  const activePluginStrategyIds = usePluginStrategyIds();
  // 已保存的策略即使没有启用的插件提供，也要列出才能显示原标识。
  const pluginStrategyIds = buildPluginStrategyIds([
    ...activePluginStrategyIds,
    form.strategy,
  ]);
  const groupMode = form.route_group_id ? "alias" : "direct";
  const isContextWindowInvalid =
    parseContextWindowInput(form.context_window) === undefined;
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
                onValueChange={(strategy) =>
                  setForm((current) => ({ ...current, strategy }))
                }
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
                    {pluginStrategyIds.map((strategy) => (
                      <SelectItem key={strategy} value={strategy}>
                        <span className="font-mono">{strategy}</span>
                      </SelectItem>
                    ))}
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
                    ? "仅用于未单独设置上下文的成员；超出时跳过，均未设置则不筛选。"
                    : "Applies to members without their own window; skip when exceeded, and ignore filtering if none is set."}
              </p>
            </SettingsRow>

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
