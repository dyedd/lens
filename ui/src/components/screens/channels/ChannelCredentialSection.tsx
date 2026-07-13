import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import type { FormCredential, Locale } from "./channelShared";
import { createLocalId, credentialIndexLabel } from "./channelShared";

type Props = {
  credentials: FormCredential[];
  locale: Locale;
  onAdd: (credential: FormCredential) => void;
  onUpdate: (index: number, patch: Partial<FormCredential>) => void;
  onRemove: (index: number) => void;
};

/** Renders editable channel credentials. */
export function ChannelCredentialSection({
  credentials,
  locale,
  onAdd,
  onUpdate,
  onRemove,
}: Props) {
  return (
    <section className="grid gap-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">
          {locale === "zh-CN" ? "密钥" : "API Keys"}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            onAdd({
              id: createLocalId("credential"),
              name: "",
              api_key: "",
              enabled: true,
            })
          }
        >
          <Plus data-icon="inline-start" />
          {locale === "zh-CN" ? "添加" : "Add"}
        </Button>
      </div>
      <FieldGroup className="gap-3">
        {credentials.map((credential, index) => (
          <div
            key={credential.id}
            className="grid min-w-0 gap-3 border-b pb-3 last:border-b-0 last:pb-0 md:grid-cols-[minmax(0,1.65fr)_minmax(0,0.85fr)_32px_32px] md:items-end"
          >
            <FieldGroup className="min-w-0 gap-3 md:contents">
              <Field>
                <FieldLabel>{credentialIndexLabel(index, locale)}</FieldLabel>
                <Input
                  className="w-full min-w-0"
                  value={credential.api_key}
                  onChange={(event) =>
                    onUpdate(index, { api_key: event.target.value })
                  }
                  placeholder="sk-..."
                />
              </Field>
              <Field>
                <FieldLabel>
                  {locale === "zh-CN" ? "备注" : "Remark"}
                </FieldLabel>
                <Input
                  className="w-full min-w-0"
                  value={credential.name}
                  onChange={(event) =>
                    onUpdate(index, { name: event.target.value })
                  }
                  placeholder={locale === "zh-CN" ? "备注" : "Remark"}
                />
              </Field>
              <div className="flex size-8 items-center justify-center">
                <Switch
                  checked={credential.enabled}
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
              >
                <X />
              </Button>
            </FieldGroup>
          </div>
        ))}
      </FieldGroup>
    </section>
  );
}
