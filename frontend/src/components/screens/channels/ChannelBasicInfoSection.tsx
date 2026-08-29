import { ChevronsUpDown, Plus, X } from "lucide-react";
import { type Dispatch, type SetStateAction, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/Command";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { ChannelBaseUrlSection } from "./ChannelBaseUrlSection";
import { ChannelCredentialSection } from "./ChannelCredentialSection";
import type {
  FormBaseUrl,
  FormCredential,
  FormState,
  Locale,
} from "./channelTypes";

type Props = {
  form: FormState;
  locale: Locale;
  availableTags: string[];
  siteId: string | null;
  canSyncRates: boolean;
  onRateSyncingChange: (isSyncing: boolean) => void;
  setForm: Dispatch<SetStateAction<FormState>>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
  updateCredential: (
    credentialId: string,
    patch: Partial<FormCredential>,
  ) => void;
  removeCredential: (index: number) => void;
};

/** Renders the channel name, base URL, and credential fields. */
export function ChannelBasicInfoSection({
  form,
  locale,
  availableTags,
  siteId,
  canSyncRates,
  onRateSyncingChange,
  setForm,
  addBaseUrl,
  updateBaseUrl,
  removeBaseUrl,
  updateCredential,
  removeCredential,
}: Props) {
  const [tagPickerOpen, setTagPickerOpen] = useState(false);
  const [tagInput, setTagInput] = useState("");
  const suggestedTags = availableTags.filter((tag) => !form.tags.includes(tag));
  const trimmedTagInput = tagInput.trim();
  const canCreateTag =
    trimmedTagInput.length > 0 &&
    !availableTags.includes(trimmedTagInput) &&
    !form.tags.includes(trimmedTagInput);

  function addTag(value: string) {
    const tag = value.trim();
    if (!tag) return;
    setForm((current) => {
      if (current.tags.length >= 20 || current.tags.includes(tag))
        return current;
      return { ...current, tags: [...current.tags, tag] };
    });
    setTagInput("");
    setTagPickerOpen(false);
  }

  return (
    <section className="grid gap-5">
      <div className="text-base font-semibold text-foreground">
        {locale === "zh-CN" ? "基本信息" : "Channel and keys"}
      </div>
      <FieldGroup className="grid gap-4 md:grid-cols-2">
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
          <Popover
            open={tagPickerOpen}
            onOpenChange={(open) => {
              setTagPickerOpen(open);
              if (!open) setTagInput("");
            }}
          >
            <PopoverTrigger asChild>
              <Button
                id="channel-tag-input"
                type="button"
                variant="outline"
                role="combobox"
                aria-controls="channel-tag-options"
                aria-expanded={tagPickerOpen}
                disabled={form.tags.length >= 20}
                className="w-full justify-between font-normal"
              >
                <span className="truncate text-muted-foreground">
                  {locale === "zh-CN"
                    ? "选择或创建标签"
                    : "Select or create a tag"}
                </span>
                <ChevronsUpDown data-icon="inline-end" />
              </Button>
            </PopoverTrigger>
            <PopoverContent
              align="start"
              className="w-[var(--radix-popover-trigger-width)] p-0"
            >
              <Command>
                <CommandInput
                  value={tagInput}
                  maxLength={80}
                  aria-label={
                    locale === "zh-CN"
                      ? "搜索或创建标签"
                      : "Search or create a tag"
                  }
                  placeholder={
                    locale === "zh-CN"
                      ? "搜索或输入新标签..."
                      : "Search or enter a new tag..."
                  }
                  onValueChange={setTagInput}
                />
                <CommandList id="channel-tag-options">
                  <CommandEmpty>
                    {trimmedTagInput && form.tags.includes(trimmedTagInput)
                      ? locale === "zh-CN"
                        ? "该标签已添加"
                        : "Tag already added"
                      : locale === "zh-CN"
                        ? "暂无已有标签"
                        : "No existing tags"}
                  </CommandEmpty>
                  {suggestedTags.length ? (
                    <CommandGroup
                      heading={
                        locale === "zh-CN" ? "已有标签" : "Existing tags"
                      }
                    >
                      {suggestedTags.map((tag) => (
                        <CommandItem
                          key={tag}
                          value={tag}
                          onSelect={() => addTag(tag)}
                        >
                          <span className="truncate">{tag}</span>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  ) : null}
                  {canCreateTag ? (
                    <CommandGroup
                      heading={locale === "zh-CN" ? "新建" : "Create"}
                    >
                      <CommandItem
                        value={`create ${trimmedTagInput}`}
                        forceMount
                        onSelect={() => addTag(trimmedTagInput)}
                      >
                        <Plus />
                        <span className="truncate">
                          {locale === "zh-CN"
                            ? `创建标签“${trimmedTagInput}”`
                            : `Create tag “${trimmedTagInput}”`}
                        </span>
                      </CommandItem>
                    </CommandGroup>
                  ) : null}
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </Field>
        {form.tags.length ? (
          <div className="flex flex-wrap gap-1.5 md:col-span-2">
            {form.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="pr-1">
                {tag}
                <button
                  type="button"
                  className="inline-flex size-4 items-center justify-center rounded-full outline-none hover:text-destructive focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={
                    locale === "zh-CN" ? `移除标签 ${tag}` : `Remove tag ${tag}`
                  }
                  onClick={() =>
                    setForm((current) => ({
                      ...current,
                      tags: current.tags.filter((item) => item !== tag),
                    }))
                  }
                >
                  <X size={12} />
                </button>
              </Badge>
            ))}
          </div>
        ) : null}
        <div className="grid gap-4 md:col-span-2 xl:grid-cols-2">
          <ChannelBaseUrlSection
            baseUrls={form.base_urls}
            locale={locale}
            onAdd={addBaseUrl}
            onUpdate={updateBaseUrl}
            onRemove={removeBaseUrl}
          />
          <ChannelCredentialSection
            baseUrls={form.base_urls}
            credentials={form.credentials}
            protocolConfigs={form.protocolConfigs}
            siteId={siteId}
            canSyncRates={canSyncRates}
            locale={locale}
            onSyncingChange={onRateSyncingChange}
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
