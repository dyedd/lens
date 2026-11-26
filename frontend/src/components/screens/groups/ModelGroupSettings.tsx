import type { Dispatch, ReactNode, SetStateAction } from "react";
import { SettingsHint } from "@/components/settings/SettingsSectionCard";
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
import type { ModelGroup } from "@/lib/api/groups";
import { parseContextWindowInput } from "@/lib/contextWindow";
import type { FormState } from "./groupTypes";
import { compileRegexRulePattern } from "./modelGroupMatching";

interface ModelGroupSettingsProps {
  locale: "zh-CN" | "en-US";
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  routeTargetOptions: ModelGroup[];
}

function SettingsRow({
  children,
  htmlFor,
  label,
  required = false,
  hint,
}: {
  children: ReactNode;
  htmlFor?: string;
  label: string;
  required?: boolean;
  hint?: string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex items-center gap-1">
        <Label
          htmlFor={htmlFor}
          required={required}
          className="text-[13px] leading-5 font-medium text-foreground/85"
        >
          {label}
        </Label>
        {hint ? <SettingsHint description={hint} /> : null}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1">{children}</div>
    </div>
  );
}

export function ModelGroupSettings({
  locale,
  form,
  setForm,
  routeTargetOptions,
}: ModelGroupSettingsProps) {
  const isZh = locale === "zh-CN";
  const groupMode = form.route_group_id ? "alias" : "direct";
  const isContextWindowInvalid =
    parseContextWindowInput(form.context_window) === undefined;
  const matchRegex = form.match_regex.trim();
  const isMatchRegexInvalid =
    Boolean(matchRegex) && !compileRegexRulePattern(matchRegex);

  function changeRouteTarget(routeGroupId: string) {
    setForm((current) => ({
      ...current,
      route_group_id: routeGroupId,
      fallback_group_ids: routeGroupId ? [] : current.fallback_group_ids,
    }));
  }

  function handleModeChange(mode: "direct" | "alias") {
    if (mode === "direct") {
      changeRouteTarget("");
    } else {
      const firstTarget = routeTargetOptions[0]?.id ?? "";
      changeRouteTarget(firstTarget);
    }
  }

  return (
    <div className="flex shrink-0 flex-col gap-3.5">
      <SettingsRow
        htmlFor="group-name"
        label={isZh ? "模型组名称" : "Group name"}
        required
      >
        <Input
          id="group-name"
          required
          className="bg-pure/80 font-mono placeholder:font-sans dark:bg-card"
          placeholder={
            isZh
              ? "输入对外模型名，如 gpt-4o"
              : "Public model name, e.g. gpt-4o"
          }
          value={form.name}
          onChange={(event) => {
            const name = event.target.value;
            setForm((current) => ({ ...current, name }));
          }}
        />
      </SettingsRow>

      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <SettingsRow
          htmlFor="group-type"
          label={isZh ? "调度模式" : "Group type"}
        >
          <SegmentedControl
            value={groupMode}
            onValueChange={handleModeChange}
            className="w-full"
            options={[
              {
                value: "direct",
                label: isZh ? "直接调度" : "Direct",
              },
              {
                value: "alias",
                label: isZh ? "别名路由" : "Alias",
              },
            ]}
          />
        </SettingsRow>

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
              onValueChange={changeRouteTarget}
            >
              {routeTargetOptions.map((group) => (
                <ComboboxOption key={group.id} value={group.id}>
                  {group.name}
                </ComboboxOption>
              ))}
            </Combobox>
          </SettingsRow>
        ) : (
          <SettingsRow
            htmlFor="group-strategy"
            label={isZh ? "分发策略" : "Routing strategy"}
          >
            <SegmentedControl
              value={form.strategy}
              onValueChange={(value) => {
                if (value === "failover" || value === "round_robin")
                  setForm((current) => ({ ...current, strategy: value }));
              }}
              className="w-full"
              options={[
                {
                  value: "failover",
                  label: isZh ? "故障切换" : "Failover",
                },
                {
                  value: "round_robin",
                  label: isZh ? "平滑轮询" : "Round robin",
                },
              ]}
            />
          </SettingsRow>
        )}
      </div>

      {groupMode === "direct" ? (
        <div className="flex flex-col gap-3.5">
          <SettingsRow
            htmlFor="group-context-window"
            label={isZh ? "默认上下文" : "Default context"}
            hint={
              isZh
                ? "仅用于未单独设置上下文的成员；超出时跳过，均未设置则不筛选。"
                : "Applies to members without their own window; skip when exceeded, and ignore filtering if none is set."
            }
          >
            <Input
              id="group-context-window"
              className="bg-pure/80 font-mono placeholder:font-sans dark:bg-card"
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
            {isContextWindowInvalid ? (
              <p className="text-xs text-destructive">
                {isZh ? "示例：200K、1M、128000" : "e.g. 200K, 1M, 128000"}
              </p>
            ) : null}
          </SettingsRow>

          <SettingsRow
            htmlFor="group-match-regex"
            label={isZh ? "匹配规则" : "Match rules"}
            hint={
              isZh
                ? "名称按不区分大小写的包含匹配；填写正则后按逻辑关系组合。"
                : "Matches model name case-insensitively by containment; combine optional regex with AND/OR."
            }
          >
            <div className="flex h-8 min-w-0 items-center overflow-hidden rounded-md border border-input/60 bg-pure/80 focus-within:border-primary/60 focus-within:ring-[1px] focus-within:ring-primary/40 dark:bg-card">
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
                <SelectTrigger className="h-full w-auto shrink-0 gap-1 rounded-none border-0 border-r border-border/60 bg-muted/45 px-2.5 text-[13px] text-muted-foreground shadow-none focus-visible:ring-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="or">
                      {isZh ? "包含 · 或" : "Contains · OR"}
                    </SelectItem>
                    <SelectItem value="and">
                      {isZh ? "包含 · 与" : "Contains · AND"}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
              <Input
                id="group-match-regex"
                className="h-full min-w-0 flex-1 rounded-none border-0 bg-transparent px-2.5 font-mono text-[13px] shadow-none placeholder:font-sans focus-visible:ring-0"
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
            {isMatchRegexInvalid ? (
              <p className="text-xs text-destructive">
                {isZh ? "正则表达式无效" : "Invalid regex"}
              </p>
            ) : null}
          </SettingsRow>
        </div>
      ) : null}
    </div>
  );
}
