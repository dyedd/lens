import {
  Field,
  FieldContent,
  FieldDescription,
  FieldLabel,
} from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { Textarea } from "@/components/ui/Textarea";
import { titleForLocale } from "@/lib/I18nContext";

import type { GatewayGeneralSettingsProps } from "./gatewaySettingsTypes";

/** Renders the gateway proxy, CORS, compatibility, and logging fields. */
export function GatewayGeneralSettings({
  locale,
  proxyUrl,
  corsAllowOrigins,
  isRelayLogBodyEnabled,
  isModelListCompatModeEnabled,
  onProxyUrlChange,
  onCorsAllowOriginsChange,
  onRelayLogBodyEnabledChange,
  onModelListCompatModeEnabledChange,
}: GatewayGeneralSettingsProps) {
  return (
    <>
      <Field>
        <FieldLabel>
          {titleForLocale(locale, "全局代理地址", "Global proxy URL")}
        </FieldLabel>
        <Input
          value={proxyUrl}
          onChange={(event) => onProxyUrlChange(event.target.value)}
          placeholder="http://127.0.0.1:7890"
        />
      </Field>
      <Field>
        <FieldLabel>
          {titleForLocale(locale, "CORS 跨域名单", "CORS allow origins")}
        </FieldLabel>
        <Textarea
          className="min-h-[92px]"
          value={corsAllowOrigins}
          onChange={(event) => onCorsAllowOriginsChange(event.target.value)}
          placeholder={"*\nhttp://localhost:3000"}
        />
      </Field>
      <Field
        orientation="horizontal"
        className="items-center justify-between gap-4"
      >
        <FieldContent>
          <FieldLabel className="w-auto">
            {titleForLocale(
              locale,
              "模型列表兼容模式",
              "Model list compatibility mode",
            )}
          </FieldLabel>
          <FieldDescription>
            {titleForLocale(
              locale,
              "开启后 /v1/models 会以 OpenAI 格式列出全部协议模型；如果客户端不支持某协议,实际请求仍可能失败。",
              "When enabled, /v1/models lists all protocol models in OpenAI format; requests can still fail if the client cannot call a protocol.",
            )}
          </FieldDescription>
        </FieldContent>
        <Switch
          checked={isModelListCompatModeEnabled}
          onCheckedChange={onModelListCompatModeEnabledChange}
        />
      </Field>
      <Field
        orientation="horizontal"
        className="items-center justify-between gap-4"
      >
        <FieldContent>
          <FieldLabel className="w-auto">
            {titleForLocale(locale, "记录日志正文", "Record log body")}
          </FieldLabel>
        </FieldContent>
        <Switch
          checked={isRelayLogBodyEnabled}
          onCheckedChange={onRelayLogBodyEnabledChange}
        />
      </Field>
    </>
  );
}
