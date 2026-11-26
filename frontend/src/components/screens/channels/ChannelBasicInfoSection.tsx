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
import { Field, FieldContent, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover";
import { Switch } from "@/components/ui/Switch";
import { ChannelBaseUrlSection } from "./ChannelBaseUrlSection";
import { ChannelCredentialSection } from "./ChannelCredentialSection";
import type { FormBaseUrl, FormState, Locale } from "./channelTypes";

type Props = {
  form: FormState;
  locale: Locale;
  availableTags: string[];
  siteId: string | null;
  canSyncRates: boolean;
  setForm: Dispatch<SetStateAction<FormState>>;
  addBaseUrl: () => void;
  updateBaseUrl: (index: number, patch: Partial<FormBaseUrl>) => void;
  removeBaseUrl: (index: number) => void;
};

/** Renders the channel name, base URL, and credential fields. */
export function ChannelBasicInfoSection({
  form,
  locale,
  availableTags,
  siteId,
  canSyncRates,
  setForm,
  addBaseUrl,
  updateBaseUrl,
  removeBaseUrl,
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
    <section className="min-w-0 max-w-full space-y-5">
      <div className="space-y-4">
        <div className="min-w-0 space-y-1.5">
          <Label
            htmlFor="channel-name"
            required
            className="text-[13px] font-medium text-foreground/85"
          >
            {locale === "zh-CN" ? "渠道名称" : "Channel name"}
          </Label>
          <Input
            id="channel-name"
            required
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                name: event.target.value,
              }))
            }
          />
        </div>

        <ChannelBaseUrlSection
          form={form}
          locale={locale}
          onAdd={addBaseUrl}
          onUpdate={updateBaseUrl}
          onRemove={removeBaseUrl}
        />

        <div className="min-w-0 space-y-1.5">
          <Label
            htmlFor="channel-tag-input"
            className="text-[13px] font-medium text-foreground/85"
          >
            {locale === "zh-CN" ? "标签" : "Tags"}
          </Label>
          <div className="flex flex-wrap items-center gap-1.5">
            {form.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="pr-1">
                {tag}
                <button
                  type="button"
                  className="inline-flex size-4 items-center justify-center rounded-full text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
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
                  <X className="size-3.5" />
                </button>
              </Badge>
            ))}
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
                  variant="ghost"
                  size="xs"
                  role="combobox"
                  aria-controls="channel-tag-options"
                  aria-expanded={tagPickerOpen}
                  disabled={form.tags.length >= 20}
                  className="h-6 gap-1 px-2 text-xs font-normal text-muted-foreground hover:text-foreground"
                >
                  <Plus className="size-3" />
                  <span>{locale === "zh-CN" ? "添加标签" : "Add tag"}</span>
                  <ChevronsUpDown className="size-3 opacity-60" />
                </Button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-60 p-0">
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
                        ? "搜索已有标签或输入新标签..."
                        : "Search existing tags or enter a new one..."
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
                          ? "没有匹配的标签"
                          : "No matching tags"}
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
          </div>
        </div>
      </div>

      <div className="border-t border-border/50 pt-5">
        <ChannelCredentialSection
          locale={locale}
          inputId="channel-keys"
          required={!siteId}
          form={form}
          setForm={setForm}
          siteId={siteId}
          canSyncRates={canSyncRates}
        />
      </div>

      <Field orientation="horizontal" className="pt-2">
        <FieldContent>
          <FieldLabel htmlFor="channel-model-listing">
            {locale === "zh-CN" ? "支持获取模型列表" : "Supports model listing"}
          </FieldLabel>
        </FieldContent>
        <Switch
          size="sm"
          id="channel-model-listing"
          checked={form.supports_model_listing}
          onCheckedChange={(checked) =>
            setForm((current) => ({
              ...current,
              supports_model_listing: checked,
            }))
          }
        />
      </Field>
    </section>
  );
}
