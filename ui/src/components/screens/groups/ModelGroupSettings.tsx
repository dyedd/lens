import type { Dispatch, SetStateAction } from "react";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { ProtocolMultiSelect } from "@/components/ui/ProtocolMultiSelect";
import { Separator } from "@/components/ui/Separator";
import type { ModelGroup, ProtocolKind } from "@/lib/api";
import { protocolOptions } from "@/lib/protocols";
import { EditablePriceRow, StrategyToggle } from "./ModelGroupEditorFields";
import type { FormState } from "./modelGroupUtils";

interface ModelGroupSettingsProps {
  locale: "zh-CN" | "en-US";
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  toggleProtocol: (protocol: ProtocolKind) => void;
  routeTargetOptions: ModelGroup[];
  changeRouteTarget: (routeGroupId: string) => void;
}

/** Render model group identity, routing, strategy, and pricing fields. */
export function ModelGroupSettings({
  locale,
  form,
  setForm,
  toggleProtocol,
  routeTargetOptions,
  changeRouteTarget,
}: ModelGroupSettingsProps) {
  return (
    <>
      <section className="grid gap-4">
        <div className="text-base font-semibold text-foreground">
          {locale === "zh-CN" ? "基本信息" : "Group settings"}
        </div>
        <FieldGroup className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "协议" : "External Protocols"}
            </FieldLabel>
            <ProtocolMultiSelect
              value={form.protocols}
              onChange={(next) => {
                const changedProtocols = protocolOptions(locale)
                  .map((option) => option.value)
                  .filter(
                    (protocol) =>
                      form.protocols.includes(protocol) !==
                      next.includes(protocol),
                  );
                if (changedProtocols.length === 1) {
                  toggleProtocol(changedProtocols[0]);
                  return;
                }
                setForm((current) => ({ ...current, protocols: next }));
              }}
              locale={locale}
              invalid={form.protocols.length === 0}
            />
            {form.protocols.length === 0 ? (
              <p className="text-sm text-destructive">
                {locale === "zh-CN"
                  ? "至少需要选择一项协议。"
                  : "At least one protocol is required."}
              </p>
            ) : null}
          </Field>
          <Field>
            <FieldLabel htmlFor="group-name">
              {locale === "zh-CN" ? "模型组名称" : "Group name"}
            </FieldLabel>
            <Input
              id="group-name"
              placeholder={
                locale === "zh-CN" ? "输入模型组名称" : "Enter group name"
              }
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  name: event.target.value,
                }))
              }
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
            <FieldLabel>
              {locale === "zh-CN" ? "模型组策略" : "Group strategy"}
            </FieldLabel>
            <StrategyToggle
              value={form.strategy}
              locale={locale}
              disabled={Boolean(form.route_group_id)}
              onChange={(value) =>
                setForm((current) => ({ ...current, strategy: value }))
              }
            />
          </Field>
        </FieldGroup>
      </section>

      {!form.route_group_id ? (
        <>
          <Separator />
          <section className="grid gap-4">
            <div className="text-base font-semibold text-foreground">
              {locale === "zh-CN" ? "价格" : "Pricing"}
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              <EditablePriceRow
                locale={locale}
                primaryLabel="input"
                primaryValue={form.input_price_per_million}
                secondaryLabel="cache_read"
                secondaryValue={form.cache_read_price_per_million}
                onPrimaryChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    input_price_per_million: value,
                  }))
                }
                onSecondaryChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    cache_read_price_per_million: value,
                  }))
                }
              />
              <EditablePriceRow
                locale={locale}
                primaryLabel="output"
                primaryValue={form.output_price_per_million}
                secondaryLabel="cache_write"
                secondaryValue={form.cache_write_price_per_million}
                onPrimaryChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    output_price_per_million: value,
                  }))
                }
                onSecondaryChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    cache_write_price_per_million: value,
                  }))
                }
              />
            </div>
          </section>
        </>
      ) : null}
    </>
  );
}
