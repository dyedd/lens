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
import type { ProtocolKind } from "@/lib/api/protocols";
import { ChannelCredentialSection } from "./ChannelCredentialSection";
import { ProtocolDropdown } from "./ProtocolDropdown";
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

  function endpointProtocols(baseUrlId: string) {
    return (
      form.protocolConfigs.find((config) => config.base_url_id === baseUrlId)
        ?.protocols ?? []
    );
  }

  function updateEndpointProtocols(
    baseUrlId: string,
    protocols: ProtocolKind[],
  ) {
    setForm((current) => ({
      ...current,
      protocolConfigs: current.protocolConfigs.map((config) =>
        config.base_url_id === baseUrlId
          ? {
              ...config,
              protocols,
              models: config.models
                .map((model) => ({
                  ...model,
                  protocols: model.protocols.filter((protocol) =>
                    protocols.includes(protocol),
                  ),
                }))
                .filter((model) => model.protocols.length > 0),
            }
          : config,
      ),
    }));
  }

  function endpointLabel(kind: FormBaseUrl["kind"]) {
    if (kind === "protocol") {
      return locale === "zh-CN" ? "协议专用" : "Protocol";
    }
    if (kind === "china") return locale === "zh-CN" ? "国内地址" : "China";
    return locale === "zh-CN" ? "默认地址" : "Default";
  }

  function protocolEditor(baseUrl: FormBaseUrl) {
    return (
      <ProtocolDropdown
        value={endpointProtocols(baseUrl.id)}
        locale={locale}
        onChange={(protocols) => updateEndpointProtocols(baseUrl.id, protocols)}
      />
    );
  }

  return (
    <div className="min-w-0 space-y-1">
      <Label
        htmlFor="channel-url"
        required
        className="text-xs font-normal text-muted-foreground"
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
      <div className="grid gap-1.5 sm:grid-cols-[minmax(0,1fr)_8rem]">
        {protocolEditor(primary)}
        <div className="flex h-8 items-center px-2 text-xs text-muted-foreground">
          {locale === "zh-CN" ? "主地址" : "Primary"}
        </div>
      </div>
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
                    <Select
                      value={baseUrl.kind}
                      onValueChange={(value) =>
                        onUpdate(index, {
                          kind: value as FormBaseUrl["kind"],
                        })
                      }
                    >
                      <SelectTrigger className="h-7 w-24 shrink-0 px-2 text-xs">
                        <SelectValue>{endpointLabel(baseUrl.kind)}</SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="default">
                          {locale === "zh-CN" ? "默认地址" : "Default"}
                        </SelectItem>
                        <SelectItem value="protocol">
                          {locale === "zh-CN" ? "协议专用地址" : "Protocol endpoint"}
                        </SelectItem>
                        <SelectItem value="china">
                          {locale === "zh-CN" ? "国内地址" : "China"}
                        </SelectItem>
                      </SelectContent>
                    </Select>
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
                      {locale === "zh-CN"
                        ? "共用主地址密钥"
                        : "Use primary keys"}
                    </label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="size-6 shrink-0 text-muted-foreground hover:text-foreground"
                      aria-label={
                        locale === "zh-CN"
                          ? "删除地址"
                          : "Remove endpoint"
                      }
                      onClick={() => onRemove(index)}
                    >
                      <Trash2 className="size-3.5 stroke-1" />
                    </Button>
                  </div>
                  {protocolEditor(baseUrl)}
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
              {locale === "zh-CN" ? "添加地址" : "Add endpoint"}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
