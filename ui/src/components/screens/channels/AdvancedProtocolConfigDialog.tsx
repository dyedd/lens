import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { FormProtocolConfig, HeaderItem, Locale } from "./channelShared";

type Props = {
  open: boolean;
  protocolConfig: FormProtocolConfig | undefined;
  protocolConfigIndex: number | null;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onUpdateProtocolConfig: (
    index: number,
    patch: Partial<FormProtocolConfig>,
  ) => void;
  onUpdateProtocolConfigHeader: (
    protocolConfigIndex: number,
    headerIndex: number,
    patch: Partial<HeaderItem>,
  ) => void;
};

/** Renders advanced proxy, header, and parameter settings. */
export function AdvancedProtocolConfigDialog({
  open,
  protocolConfig,
  protocolConfigIndex,
  locale,
  onOpenChange,
  onUpdateProtocolConfig,
  onUpdateProtocolConfigHeader,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {protocolConfigIndex !== null && protocolConfig ? (
        <AppDialogContent
          className="max-w-3xl"
          title={locale === "zh-CN" ? "更多设置" : "More settings"}
        >
          <div className="grid gap-4">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="protocol-proxy-mode">
                  {locale === "zh-CN" ? "代理模式" : "Proxy mode"}
                </FieldLabel>
                <Select
                  value={protocolConfig.proxy_mode}
                  onValueChange={(value) =>
                    onUpdateProtocolConfig(protocolConfigIndex, {
                      proxy_mode: value as FormProtocolConfig["proxy_mode"],
                    })
                  }
                >
                  <SelectTrigger id="protocol-proxy-mode" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="inherit">
                        {locale === "zh-CN"
                          ? "跟随系统代理"
                          : "Use system proxy"}
                      </SelectItem>
                      <SelectItem value="direct">
                        {locale === "zh-CN" ? "不使用代理" : "Direct"}
                      </SelectItem>
                      <SelectItem value="custom">
                        {locale === "zh-CN" ? "自定义代理" : "Custom proxy"}
                      </SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              {protocolConfig.proxy_mode === "custom" ? (
                <Field>
                  <FieldLabel htmlFor="protocol-proxy">
                    {locale === "zh-CN" ? "代理地址" : "Proxy URL"}
                  </FieldLabel>
                  <Input
                    id="protocol-proxy"
                    value={protocolConfig.channel_proxy}
                    onChange={(event) =>
                      onUpdateProtocolConfig(protocolConfigIndex, {
                        channel_proxy: event.target.value,
                      })
                    }
                    placeholder="http://127.0.0.1:7890"
                  />
                </Field>
              ) : null}
            </FieldGroup>
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-foreground">
                  {locale === "zh-CN" ? "请求头" : "Headers"}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    onUpdateProtocolConfig(protocolConfigIndex, {
                      headers: [
                        ...protocolConfig.headers,
                        { key: "", value: "" },
                      ],
                    })
                  }
                >
                  <Plus data-icon="inline-start" />
                  {locale === "zh-CN" ? "添加" : "Add"}
                </Button>
              </div>
              {protocolConfig.headers.map((header, headerIndex) => (
                <div
                  key={headerIndex}
                  className="grid gap-3 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
                >
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "请求头名称" : "Header key"}
                    </FieldLabel>
                    <Input
                      value={header.key}
                      onChange={(event) =>
                        onUpdateProtocolConfigHeader(
                          protocolConfigIndex,
                          headerIndex,
                          { key: event.target.value },
                        )
                      }
                      placeholder={
                        locale === "zh-CN" ? "请求头名称" : "Header-Key"
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "请求头值" : "Header value"}
                    </FieldLabel>
                    <Input
                      value={header.value}
                      onChange={(event) =>
                        onUpdateProtocolConfigHeader(
                          protocolConfigIndex,
                          headerIndex,
                          { value: event.target.value },
                        )
                      }
                      placeholder={
                        locale === "zh-CN" ? "请求头值" : "Header-Value"
                      }
                    />
                  </Field>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="text-muted-foreground"
                    onClick={() =>
                      onUpdateProtocolConfig(protocolConfigIndex, {
                        headers:
                          protocolConfig.headers.length > 1
                            ? protocolConfig.headers.filter(
                                (_, currentIndex) =>
                                  currentIndex !== headerIndex,
                              )
                            : protocolConfig.headers,
                      })
                    }
                  >
                    <X />
                  </Button>
                </div>
              ))}
            </div>
            <Field>
              <FieldLabel htmlFor="protocol-param-override">
                {locale === "zh-CN" ? "参数覆盖" : "Param Override"}
              </FieldLabel>
              <Textarea
                id="protocol-param-override"
                className="min-h-24"
                value={protocolConfig.param_override}
                onChange={(event) =>
                  onUpdateProtocolConfig(protocolConfigIndex, {
                    param_override: event.target.value,
                  })
                }
              />
              <FieldDescription>
                {locale === "zh-CN"
                  ? "填写 JSON 片段用于覆盖请求参数。"
                  : "Use a JSON snippet to override request params."}
              </FieldDescription>
            </Field>
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}
