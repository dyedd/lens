"use client";

import { useState, type Dispatch, type SetStateAction } from "react";
import { Plus, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
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
  const [tagInput, setTagInput] = useState("");

  function addTag() {
    const tag = tagInput.trim();
    if (!tag) return;
    setForm((current) => {
      if (current.tags.length >= 20 || current.tags.includes(tag))
        return current;
      return { ...current, tags: [...current.tags, tag] };
    });
    setTagInput("");
  }

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
        <Field>
          <FieldLabel htmlFor="channel-tag-input">
            {locale === "zh-CN" ? "标签" : "Tags"}
          </FieldLabel>
          <div className="flex gap-2">
            <Input
              id="channel-tag-input"
              value={tagInput}
              maxLength={80}
              placeholder={locale === "zh-CN" ? "新标签" : "New tag"}
              disabled={form.tags.length >= 20}
              onChange={(event) => setTagInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return;
                event.preventDefault();
                addTag();
              }}
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label={locale === "zh-CN" ? "添加标签" : "Add tag"}
              disabled={!tagInput.trim() || form.tags.length >= 20}
              onClick={addTag}
            >
              <Plus />
            </Button>
          </div>
          {form.tags.length ? (
            <div className="flex flex-wrap gap-1.5">
              {form.tags.map((tag) => (
                <Badge key={tag} variant="secondary" className="pr-1">
                  {tag}
                  <button
                    type="button"
                    className="inline-flex rounded-full outline-none hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring"
                    aria-label={
                      locale === "zh-CN"
                        ? `移除标签 ${tag}`
                        : `Remove tag ${tag}`
                    }
                    onClick={() =>
                      setForm((current) => ({
                        ...current,
                        tags: current.tags.filter((item) => item !== tag),
                      }))
                    }
                  >
                    <X />
                  </button>
                </Badge>
              ))}
            </div>
          ) : null}
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
