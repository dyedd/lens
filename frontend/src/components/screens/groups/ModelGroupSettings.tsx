import type { Dispatch, SetStateAction } from "react";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
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
  return (
    <div className="flex shrink-0 flex-col gap-5">
      <section className="grid gap-4">
        <FieldGroup className="grid gap-4 sm:grid-cols-2">
          <Field className="sm:col-span-2">
            <FieldLabel htmlFor="group-name" required>
              {locale === "zh-CN" ? "模型组名称" : "Group name"}
            </FieldLabel>
            <Input
              id="group-name"
              required
              className="font-mono"
              placeholder={
                locale === "zh-CN" ? "输入对外模型名" : "Public model name"
              }
              value={form.name}
              onChange={(event) => changeName(event.target.value)}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="group-route-target">
              {locale === "zh-CN" ? "路由目标模型组" : "Route target group"}
            </FieldLabel>
            <Combobox
              id="group-route-target"
              className="w-full"
              value={form.route_group_id}
              onChange={(event) => changeRouteTarget(event.target.value)}
            >
              <ComboboxOption value="">
                {locale === "zh-CN" ? "不启用模型组路由" : "No group routing"}
              </ComboboxOption>
              {routeTargetOptions.map((group) => (
                <ComboboxOption key={group.id} value={group.id}>
                  {group.name}
                </ComboboxOption>
              ))}
            </Combobox>
          </Field>
          <Field>
            <FieldLabel htmlFor="group-strategy">
              {locale === "zh-CN" ? "模型组策略" : "Group strategy"}
            </FieldLabel>
            <Select
              value={form.strategy}
              disabled={Boolean(form.route_group_id)}
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
                    {locale === "zh-CN" ? "故障转移" : "Failover"}
                  </SelectItem>
                  <SelectItem value="round_robin">
                    {locale === "zh-CN" ? "轮询" : "Round robin"}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
        </FieldGroup>
      </section>
    </div>
  );
}
