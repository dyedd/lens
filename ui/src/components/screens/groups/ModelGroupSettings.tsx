import type { Dispatch, SetStateAction } from "react";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Separator } from "@/components/ui/Separator";
import type { ModelGroup } from "@/lib/api";
import { EditablePriceRow, StrategyToggle } from "./ModelGroupEditorFields";
import type { FormState } from "./modelGroupUtils";

interface ModelGroupSettingsProps {
  locale: "zh-CN" | "en-US";
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  routeTargetOptions: ModelGroup[];
  changeRouteTarget: (routeGroupId: string) => void;
}

/** Render model group identity, routing, strategy, and pricing fields. */
export function ModelGroupSettings({
  locale,
  form,
  setForm,
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
              {form.pricing_mode === "non_tokens" ? (
                <Field>
                  <FieldLabel>
                    {locale === "zh-CN"
                      ? "$image（每张）"
                      : "$image (per image)"}
                  </FieldLabel>
                  <Input
                    value={form.image_price_per_image}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        image_price_per_image: event.target.value,
                      }))
                    }
                  />
                </Field>
              ) : (
                <>
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
                </>
              )}
            </div>
          </section>
        </>
      ) : null}
    </>
  );
}
