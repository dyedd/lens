import { ChevronDown, Plus, Trash2 } from "lucide-react";
import { type Dispatch, type SetStateAction, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { cn } from "@/lib/classNames";
import { ChannelCredentialSection } from "./ChannelCredentialSection";
import type { FormBaseUrl, FormState, Locale } from "./channelTypes";

type Props = {
  form: FormState;
  locale: Locale;
  siteId: string | null;
  canSyncRates: boolean;
  setForm: Dispatch<SetStateAction<FormState>>;
  onAdd: () => void;
  onUpdate: (index: number, patch: Partial<FormBaseUrl>) => void;
  onRemove: (index: number) => void;
};

/** Renders the primary channel URL and optional extra endpoints. */
export function ChannelBaseUrlSection({
  form,
  locale,
  siteId,
  canSyncRates,
  setForm,
  onAdd,
  onUpdate,
  onRemove,
}: Props) {
  const primary = form.base_urls[0];
  const extraUrls = form.base_urls.slice(1);
  const [extraOpen, setExtraOpen] = useState(extraUrls.length > 0);
  if (!primary) return null;

  return (
    <div className="min-w-0 space-y-1">
      <Label
        htmlFor="channel-url"
        required
        className="text-xs font-normal text-muted-foreground"
      >
        {locale === "zh-CN" ? "地址" : "URL"}
      </Label>
      <Input
        id="channel-url"
        required
        placeholder="https://api.example.com/v1"
        value={primary.url}
        onChange={(event) => onUpdate(0, { url: event.target.value })}
      />
      <div className="pt-1">
        <button
          type="button"
          className="flex h-8 w-full items-center justify-between rounded-md text-left text-xs font-normal text-muted-foreground hover:text-foreground"
          onClick={() => {
            if (!extraOpen && extraUrls.length === 0) onAdd();
            setExtraOpen((open) => !open);
          }}
        >
          <span>
            {locale === "zh-CN" ? "更多地址" : "More URLs"}
            {extraUrls.length
              ? locale === "zh-CN"
                ? `（${extraUrls.length}）`
                : ` (${extraUrls.length})`
              : ""}
          </span>
          <ChevronDown
            className={cn(
              "size-3.5 stroke-1 transition-transform",
              extraOpen && "rotate-180",
            )}
          />
        </button>
        {extraOpen ? (
          <div className="space-y-3 pt-1">
            {extraUrls.map((baseUrl, extraIndex) => {
              const index = extraIndex + 1;
              const shareKeys = baseUrl.shareKeys !== false;
              return (
                <div
                  key={baseUrl.id}
                  className="space-y-2 rounded-md bg-muted/35 p-2.5"
                >
                  <div className="flex items-center gap-2">
                    <Input
                      className="min-w-0 flex-1"
                      value={baseUrl.url}
                      placeholder="https://api.example.com/v1"
                      onChange={(event) =>
                        onUpdate(index, { url: event.target.value })
                      }
                    />
                    <label
                      htmlFor={`share-keys-${baseUrl.id}`}
                      className="flex shrink-0 items-center gap-1.5 whitespace-nowrap text-xs text-muted-foreground"
                    >
                      <Checkbox
                        id={`share-keys-${baseUrl.id}`}
                        checked={shareKeys}
                        onCheckedChange={(checked) => {
                          const nextShare = checked === true;
                          setForm((current) => ({
                            ...current,
                            base_urls: current.base_urls.map(
                              (item, itemIndex) =>
                                itemIndex === index
                                  ? {
                                      ...item,
                                      shareKeys: nextShare,
                                      newApiKeysLines: nextShare
                                        ? ""
                                        : item.newApiKeysLines,
                                    }
                                  : item,
                            ),
                            credentials: nextShare
                              ? current.credentials.filter(
                                  (item) => item.baseUrlId !== baseUrl.id,
                                )
                              : current.credentials,
                          }));
                        }}
                      />
                      {locale === "zh-CN" ? "使用相同密钥" : "Same keys"}
                    </label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="size-6 shrink-0 text-muted-foreground hover:text-foreground"
                      aria-label={
                        locale === "zh-CN" ? "删除地址" : "Remove URL"
                      }
                      onClick={() => onRemove(index)}
                    >
                      <Trash2 className="size-3.5 stroke-1" />
                    </Button>
                  </div>
                  {shareKeys ? null : (
                    <ChannelCredentialSection
                      locale={locale}
                      inputId={`channel-keys-${baseUrl.id}`}
                      required={!siteId}
                      baseUrlId={baseUrl.id}
                      form={form}
                      setForm={setForm}
                      siteId={siteId}
                      canSyncRates={canSyncRates}
                    />
                  )}
                </div>
              );
            })}
            <Button
              type="button"
              variant="ghost"
              size="xs"
              className="h-7 px-2 text-xs font-normal text-muted-foreground"
              onClick={onAdd}
            >
              <Plus className="size-3.5 stroke-1" />
              {locale === "zh-CN" ? "添加地址" : "Add URL"}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
