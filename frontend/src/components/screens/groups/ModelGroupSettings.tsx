import type { Dispatch, SetStateAction } from "react";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
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

import type { FormState } from "./groupTypes";

interface ModelGroupSettingsProps {
  locale: "zh-CN" | "en-US";
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  changeName: (name: string) => void;
  routeTargetOptions: ModelGroup[];
  changeRouteTarget: (routeGroupId: string) => void;
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

  function handleModeChange(mode: "direct" | "alias") {
    if (mode === "direct") {
      changeRouteTarget("");
    } else {
      const firstTarget = routeTargetOptions[0]?.id ?? "";
      changeRouteTarget(firstTarget);
    }
  }

  return (
    <div className="flex shrink-0 flex-col gap-5">
      <section className="grid gap-4">
        <FieldGroup className="grid gap-4 sm:grid-cols-2">
          <Field className="sm:col-span-2">
            <FieldLabel htmlFor="group-name" required>
              {isZh ? "模型组名称" : "Group name"}
            </FieldLabel>
            <Input
              id="group-name"
              required
              className="font-mono"
              placeholder={
                isZh
                  ? "输入对外模型名，如 gpt-4o"
                  : "Public model name, e.g. gpt-4o"
              }
              value={form.name}
              onChange={(event) => changeName(event.target.value)}
            />
          </Field>

          <Field className="sm:col-span-2 space-y-1.5">
            <FieldLabel>{isZh ? "模型组类型" : "Group type"}</FieldLabel>
            <SegmentedControl
              value={groupMode}
              onValueChange={handleModeChange}
              options={[
                {
                  value: "direct",
                  label: isZh ? "直接调度" : "Direct execution",
                },
                {
                  value: "alias",
                  label: isZh ? "别名" : "Alias",
                },
              ]}
            />
            <FieldDescription>
              {groupMode === "direct"
                ? isZh
                  ? "直接管理渠道成员和分发策略。"
                  : "Manage channel members and the distribution strategy directly."
                : isZh
                  ? "作为别名转发到目标模型组，共用它的渠道成员。"
                  : "Forward requests to the target model group and share its channel members."}
            </FieldDescription>
          </Field>

          {groupMode === "alias" ? (
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="group-route-target" required>
                {isZh ? "目标模型组" : "Target model group"}
              </FieldLabel>
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
            </Field>
          ) : (
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="group-strategy">
                {isZh ? "分发策略" : "Routing strategy"}
              </FieldLabel>
              <Select
                value={form.strategy}
                onValueChange={(value) => {
                  if (value === "failover" || value === "round_robin")
                    setForm((current) => ({ ...current, strategy: value }));
                }}
              >
                <SelectTrigger id="group-strategy">
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
            </Field>
          )}
        </FieldGroup>
      </section>
    </div>
  );
}
