import type { Dispatch, SetStateAction } from "react";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { ChannelBaseUrlSection } from "./ChannelBaseUrlSection";
import { ChannelCredentialSection } from "./ChannelCredentialSection";
import type {
  FormBaseUrl,
  FormCredential,
  FormState,
  Locale,
} from "./channelShared";

type Props = {
  form: FormState;
  locale: Locale;
  setForm: Dispatch<SetStateAction<FormState>>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
  updateCredential: (index: number, patch: Partial<FormCredential>) => void;
  removeCredential: (index: number) => void;
};

/** Renders the channel name, base URL, and credential fields. */
export function ChannelBasicInfoSection({
  form,
  locale,
  setForm,
  addBaseUrl,
  updateBaseUrl,
  removeBaseUrl,
  updateCredential,
  removeCredential,
}: Props) {
  return (
    <section className="grid gap-5">
      <div className="text-base font-semibold text-foreground">
        {locale === "zh-CN" ? "基本信息" : "Channel and keys"}
      </div>
      <FieldGroup className="gap-4">
        <Field>
          <FieldLabel htmlFor="channel-name">
            {locale === "zh-CN" ? "渠道名称" : "Channel name"}
          </FieldLabel>
          <Input
            id="channel-name"
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                name: event.target.value,
              }))
            }
          />
        </Field>
        <div className="grid gap-4 xl:grid-cols-2">
          <ChannelBaseUrlSection
            baseUrls={form.base_urls}
            locale={locale}
            onAdd={addBaseUrl}
            onUpdate={updateBaseUrl}
            onRemove={removeBaseUrl}
          />
          <ChannelCredentialSection
            credentials={form.credentials}
            locale={locale}
            onAdd={(credential) =>
              setForm((current) => ({
                ...current,
                credentials: [...current.credentials, credential],
              }))
            }
            onUpdate={updateCredential}
            onRemove={removeCredential}
          />
        </div>
      </FieldGroup>
    </section>
  );
}
