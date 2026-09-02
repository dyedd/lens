import { HeaderRows } from "@/components/ruleEditors/HeaderRows";
import { ParamRuleRows } from "@/components/ruleEditors/ParamRuleRows";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { titleForLocale } from "@/lib/I18nContext";
import type { FormProtocolConfig, Locale } from "./channelTypes";

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
};

/** Renders proxy, header, and parameter rules for a protocol configuration. */
export function AdvancedProtocolConfigDialog({
  open,
  protocolConfig,
  protocolConfigIndex,
  locale,
  onOpenChange,
  onUpdateProtocolConfig,
}: Props) {
  if (protocolConfigIndex === null || !protocolConfig)
    return <Dialog open={open} onOpenChange={onOpenChange} />;
  const update = (patch: Partial<FormProtocolConfig>) =>
    onUpdateProtocolConfig(protocolConfigIndex, patch);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <AppDialogContent
        className="max-w-3xl"
        title={titleForLocale(locale, "更多设置", "More settings")}
      >
        <div className="grid max-h-[75dvh] gap-4 overflow-y-auto pr-1">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="protocol-proxy-mode">
                {titleForLocale(locale, "代理模式", "Proxy mode")}
              </FieldLabel>
              <Select
                value={protocolConfig.proxy_mode}
                onValueChange={(value) =>
                  update({
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
                      {titleForLocale(
                        locale,
                        "跟随系统代理",
                        "Use system proxy",
                      )}
                    </SelectItem>
                    <SelectItem value="direct">
                      {titleForLocale(locale, "不使用代理", "Direct")}
                    </SelectItem>
                    <SelectItem value="custom">
                      {titleForLocale(locale, "自定义代理", "Custom proxy")}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            {protocolConfig.proxy_mode === "custom" ? (
              <Field>
                <FieldLabel htmlFor="protocol-proxy">
                  {titleForLocale(locale, "代理地址", "Proxy URL")}
                </FieldLabel>
                <Input
                  id="protocol-proxy"
                  value={protocolConfig.channel_proxy}
                  onChange={(event) =>
                    update({ channel_proxy: event.target.value })
                  }
                  placeholder="http://127.0.0.1:7890"
                />
              </Field>
            ) : null}
          </FieldGroup>
          <HeaderRows
            title={titleForLocale(locale, "请求头", "Headers")}
            headers={protocolConfig.headers}
            locale={locale}
            onAdd={() =>
              update({
                headers: [
                  ...protocolConfig.headers,
                  { key: "", value: "", action: "override" },
                ],
              })
            }
            onUpdate={(index, patch) =>
              update({
                headers: protocolConfig.headers.map((header, currentIndex) =>
                  currentIndex === index ? { ...header, ...patch } : header,
                ),
              })
            }
            onRemove={(index) =>
              update({
                headers:
                  protocolConfig.headers.length > 1
                    ? protocolConfig.headers.filter(
                        (_, currentIndex) => currentIndex !== index,
                      )
                    : protocolConfig.headers,
              })
            }
          />
          <ParamRuleRows
            title={titleForLocale(locale, "参数规则", "Parameter rules")}
            locale={locale}
            rules={protocolConfig.param_override}
            onChange={(rules) =>
              update({
                param_override: rules,
              })
            }
          />
        </div>
      </AppDialogContent>
    </Dialog>
  );
}
