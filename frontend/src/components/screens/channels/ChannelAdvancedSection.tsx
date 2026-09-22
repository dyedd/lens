import { ChevronDown, ListPlus } from "lucide-react";
import { type Dispatch, type SetStateAction, useState } from "react";
import { toast } from "sonner";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/Accordion";
import { Button } from "@/components/ui/Button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/DropdownMenu";
import { Input } from "@/components/ui/Input";
import { JsonField } from "@/components/ui/JsonField";
import { Label } from "@/components/ui/Label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import type { ChannelProxyMode } from "@/lib/api/sites";
import { mergeHeaderJson } from "./channelAdvancedJson";
import type { FormState, Locale } from "./channelTypes";

type Props = {
  form: FormState;
  locale: Locale;
  setForm: Dispatch<SetStateAction<FormState>>;
};

const HEADER_PRESETS: Array<{
  key: string;
  value: string;
  zh: string;
  en: string;
}> = [
  {
    key: "anthropic-version",
    value: "2023-06-01",
    zh: "Anthropic Version",
    en: "Anthropic Version",
  },
];

const accordionTriggerClass =
  "h-11 items-center py-0 text-xs font-normal text-muted-foreground hover:text-foreground hover:no-underline data-[state=open]:font-medium data-[state=open]:text-foreground [&_.accordion-trigger-icon]:translate-y-0";

/** Renders channel proxy, header, and parameter overrides. */
export function ChannelAdvancedSection({ form, locale, setForm }: Props) {
  const [openSections, setOpenSections] = useState<string[]>([]);

  function patchForm(patch: Partial<FormState>) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function fillHeaderPreset(preset: (typeof HEADER_PRESETS)[number]) {
    const next = mergeHeaderJson(form.headersJson, {
      [preset.key]: preset.value,
    });
    if (next === null) {
      toast.error(
        locale === "zh-CN"
          ? "请先修正请求头 JSON"
          : "Fix the header JSON first",
      );
      return;
    }
    if (next === form.headersJson) {
      toast.info(
        locale === "zh-CN" ? "该请求头已存在" : "That header is already set",
      );
      return;
    }
    patchForm({ headersJson: next });
  }

  return (
    <Accordion
      type="multiple"
      value={openSections}
      onValueChange={setOpenSections}
      className="border-y border-border/60"
    >
      <AccordionItem value="proxy" className="border-border/60">
        <AccordionTrigger className={accordionTriggerClass}>
          <span>{locale === "zh-CN" ? "代理" : "Proxy"}</span>
        </AccordionTrigger>
        <AccordionContent className="space-y-4 pb-4 pt-0">
          <div className="min-w-0 space-y-1">
            <Label className="text-xs font-normal text-muted-foreground">
              {locale === "zh-CN" ? "代理模式" : "Proxy mode"}
            </Label>
            <Select
              value={form.proxy_mode}
              onValueChange={(value) =>
                patchForm({ proxy_mode: value as ChannelProxyMode })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="inherit">
                  {locale === "zh-CN" ? "跟随系统代理" : "Use system proxy"}
                </SelectItem>
                <SelectItem value="direct">
                  {locale === "zh-CN" ? "不使用代理" : "Direct"}
                </SelectItem>
                <SelectItem value="custom">
                  {locale === "zh-CN" ? "自定义代理" : "Custom proxy"}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          {form.proxy_mode === "custom" ? (
            <div className="min-w-0 space-y-1">
              <Label
                htmlFor="channel-proxy"
                className="text-xs font-normal text-muted-foreground"
              >
                {locale === "zh-CN" ? "代理地址" : "Proxy URL"}
              </Label>
              <Input
                id="channel-proxy"
                placeholder="http://127.0.0.1:7890"
                value={form.channel_proxy}
                onChange={(event) =>
                  patchForm({ channel_proxy: event.target.value })
                }
              />
            </div>
          ) : null}
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="headers" className="border-border/60">
        <AccordionTrigger className={accordionTriggerClass}>
          <span>{locale === "zh-CN" ? "请求头" : "Headers"}</span>
        </AccordionTrigger>
        <AccordionContent className="pb-4 pt-0">
          <JsonField
            id="channel-headers"
            value={form.headersJson}
            placeholder={`{"X-Custom-Header": "value"}`}
            formatLabel={locale === "zh-CN" ? "格式化" : "Format"}
            invalidFormatMessage={
              locale === "zh-CN"
                ? "请求头 JSON 格式无效"
                : "Header JSON is invalid"
            }
            onChange={(value) => patchForm({ headersJson: value })}
            actions={
              <DropdownMenu modal={false}>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 gap-1 px-2 text-[11px]"
                  >
                    <ListPlus className="size-3" />
                    {locale === "zh-CN" ? "快捷填充" : "Quick fill"}
                    <ChevronDown className="size-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-56">
                  <DropdownMenuLabel className="text-[10px] text-muted-foreground">
                    {locale === "zh-CN" ? "常用请求头" : "Common headers"}
                  </DropdownMenuLabel>
                  {HEADER_PRESETS.map((preset) => (
                    <DropdownMenuItem
                      key={preset.key}
                      onSelect={() => fillHeaderPreset(preset)}
                    >
                      {locale === "zh-CN" ? preset.zh : preset.en}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            }
          />
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="params" className="border-border/60">
        <AccordionTrigger className={accordionTriggerClass}>
          <span>{locale === "zh-CN" ? "参数" : "Parameters"}</span>
        </AccordionTrigger>
        <AccordionContent className="pb-4 pt-0">
          <JsonField
            id="channel-params"
            value={form.paramsJson}
            placeholder={`{"temperature": 0.7}`}
            formatLabel={locale === "zh-CN" ? "格式化" : "Format"}
            invalidFormatMessage={
              locale === "zh-CN"
                ? "参数 JSON 格式无效"
                : "Parameter JSON is invalid"
            }
            onChange={(value) => patchForm({ paramsJson: value })}
          />
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
