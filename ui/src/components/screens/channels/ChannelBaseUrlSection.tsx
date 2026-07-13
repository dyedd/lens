import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import type { FormBaseUrl, Locale } from "./channelShared";
import { baseUrlIndexLabel } from "./channelShared";

type Props = {
  baseUrls: FormBaseUrl[];
  locale: Locale;
  onAdd: () => void;
  onUpdate: (index: number, patch: Partial<FormBaseUrl>) => void;
  onRemove: (index: number) => void;
};

/** Renders editable channel base URLs. */
export function ChannelBaseUrlSection({
  baseUrls,
  locale,
  onAdd,
  onUpdate,
  onRemove,
}: Props) {
  return (
    <section className="grid gap-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">
          {locale === "zh-CN" ? "请求地址" : "Base URLs"}
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          <Plus data-icon="inline-start" />
          {locale === "zh-CN" ? "添加" : "Add"}
        </Button>
      </div>
      <FieldGroup className="gap-3">
        {baseUrls.map((baseUrl, index) => (
          <div
            key={baseUrl.id}
            className="grid min-w-0 gap-3 border-b pb-3 last:border-b-0 last:pb-0"
          >
            <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1.65fr)_minmax(0,0.85fr)_32px_32px] md:items-end">
              <FieldGroup className="min-w-0 gap-3 md:contents">
                <Field>
                  <FieldLabel>{baseUrlIndexLabel(index, locale)}</FieldLabel>
                  <Input
                    className="w-full min-w-0"
                    value={baseUrl.url}
                    onChange={(event) =>
                      onUpdate(index, { url: event.target.value })
                    }
                    placeholder="https://api.example.com"
                  />
                </Field>
                <Field>
                  <FieldLabel>
                    {locale === "zh-CN" ? "备注" : "Remark"}
                  </FieldLabel>
                  <Input
                    className="w-full min-w-0"
                    value={baseUrl.name}
                    onChange={(event) =>
                      onUpdate(index, { name: event.target.value })
                    }
                    placeholder={locale === "zh-CN" ? "备注" : "Remark"}
                  />
                </Field>
                <div className="flex size-8 items-center justify-center">
                  <Switch
                    checked={baseUrl.enabled}
                    onCheckedChange={(checked) =>
                      onUpdate(index, { enabled: checked })
                    }
                  />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="text-muted-foreground"
                  onClick={() => onRemove(index)}
                  disabled={baseUrls.length <= 1}
                >
                  <X />
                </Button>
              </FieldGroup>
            </div>
          </div>
        ))}
      </FieldGroup>
    </section>
  );
}
