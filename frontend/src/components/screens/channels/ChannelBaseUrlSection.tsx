import { ChevronDown, Plus, Trash2 } from "lucide-react";
import { type Dispatch, type SetStateAction, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
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

  function endpointLabel(kind: FormBaseUrl["kind"]) {
    const labels = {
      openai_chat: ["OpenAI Chat 地址", "OpenAI Chat"],
      openai_responses: ["OpenAI Responses 地址", "OpenAI Responses"],
      openai_embedding: ["OpenAI Embeddings 地址", "OpenAI Embeddings"],
      openai_image: ["OpenAI Images 地址", "OpenAI Images"],
      anthropic: ["Anthropic 地址", "Anthropic"],
      gemini: ["Gemini 地址", "Gemini"],
      rerank: ["Rerank 地址", "Rerank"],
      models: ["模型列表地址", "Model list"],
      china: ["国内地址", "China"],
    } as const;
    if (kind === "default" || kind === "protocol") return "";
    return labels[kind][locale === "zh-CN" ? 0 : 1];
  }

  return (
    <div className="min-w-0 space-y-1">
      <Label
        htmlFor="channel-url"
        required
        className="text-sm font-normal text-muted-foreground"
      >
        {locale === "zh-CN" ? "接口地址" : "Base URL"}
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
          className="flex h-8 w-full items-center justify-between rounded-md text-left text-sm font-normal text-muted-foreground hover:text-foreground"
          onClick={() => {
            if (!extraOpen && extraUrls.length === 0) onAdd();
            setExtraOpen((open) => !open);
          }}
        >
          <span>
            {locale === "zh-CN" ? "其他地址" : "Other endpoints"}
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
                  className="grid min-w-0 grid-cols-[minmax(0,8rem)_minmax(0,1fr)_1.5rem] items-center gap-2 rounded-md bg-muted/35 p-2.5"
                >
                  <Select
                    value={baseUrl.kind}
                    onValueChange={(value) =>
                      onUpdate(index, {
                        kind: value as FormBaseUrl["kind"],
                      })
                    }
                  >
                    <SelectTrigger className="h-7 w-full min-w-0 overflow-hidden px-2">
                      <SelectValue className="min-w-0 flex-1 truncate text-left">
                        {endpointLabel(baseUrl.kind)}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai_chat">OpenAI Chat</SelectItem>
                      <SelectItem value="openai_responses">
                        OpenAI Responses
                      </SelectItem>
                      <SelectItem value="openai_embedding">
                        OpenAI Embeddings
                      </SelectItem>
                      <SelectItem value="openai_image">
                        OpenAI Images
                      </SelectItem>
                      <SelectItem value="anthropic">Anthropic</SelectItem>
                      <SelectItem value="gemini">Gemini</SelectItem>
                      <SelectItem value="rerank">Rerank</SelectItem>
                      <SelectItem value="models">
                        {locale === "zh-CN" ? "模型列表" : "Model list"}
                      </SelectItem>
                      <SelectItem value="china">
                        {locale === "zh-CN" ? "国内地址" : "China"}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    className="min-w-0"
                    value={baseUrl.url}
                    placeholder="https://api.example.com/v1"
                    onChange={(event) =>
                      onUpdate(index, { url: event.target.value })
                    }
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="size-6 justify-self-end text-muted-foreground hover:text-foreground"
                    aria-label={
                      locale === "zh-CN" ? "删除地址" : "Remove endpoint"
                    }
                    onClick={() => onRemove(index)}
                  >
                    <Trash2 className="size-3.5 stroke-1" />
                  </Button>
                  <label
                    htmlFor={`share-keys-${baseUrl.id}`}
                    className="col-span-2 flex min-w-0 items-center gap-1.5 text-sm text-muted-foreground"
                  >
                    <Checkbox
                      id={`share-keys-${baseUrl.id}`}
                      checked={shareKeys}
                      onCheckedChange={(checked) => {
                        const nextShare = checked === true;
                        setForm((current) => ({
                          ...current,
                          base_urls: current.base_urls.map((item, itemIndex) =>
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
                    {locale === "zh-CN" ? "共用主地址密钥" : "Use primary keys"}
                  </label>
                  {shareKeys ? null : (
                    <div className="col-span-2 min-w-0">
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
                    </div>
                  )}
                </div>
              );
            })}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 font-normal text-muted-foreground"
              onClick={onAdd}
            >
              <Plus className="size-3.5 stroke-1" />
              {locale === "zh-CN" ? "添加地址" : "Add endpoint"}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
