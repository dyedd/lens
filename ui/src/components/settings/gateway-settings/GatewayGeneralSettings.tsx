import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
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
  authAccessTokenMinutes,
  requestTimeoutSeconds,
  maxRequestBodyBytes,
  authAccessTokenMinutesError,
  requestTimeoutSecondsError,
  maxRequestBodyBytesError,
  isRelayLogBodyEnabled,
  isModelListCompatModeEnabled,
  onProxyUrlChange,
  onCorsAllowOriginsChange,
  onAuthAccessTokenMinutesChange,
  onRequestTimeoutSecondsChange,
  onMaxRequestBodyBytesChange,
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
      <Field data-invalid={Boolean(authAccessTokenMinutesError)}>
        <FieldLabel htmlFor="gateway-auth-access-token-minutes">
          {titleForLocale(
            locale,
            "访问令牌有效期（分钟）",
            "Access token lifetime (minutes)",
          )}
        </FieldLabel>
        <Input
          id="gateway-auth-access-token-minutes"
          type="number"
          required
          min="1"
          max="525600"
          step="1"
          value={authAccessTokenMinutes}
          aria-invalid={Boolean(authAccessTokenMinutesError)}
          aria-describedby={
            authAccessTokenMinutesError
              ? "gateway-auth-access-token-minutes-description gateway-auth-access-token-minutes-error"
              : "gateway-auth-access-token-minutes-description"
          }
          onChange={(event) =>
            onAuthAccessTokenMinutesChange(event.target.value)
          }
        />
        <FieldDescription id="gateway-auth-access-token-minutes-description">
          {titleForLocale(
            locale,
            "登录后签发的访问令牌有效期，必须大于 0。",
            "Lifetime of access tokens issued after login; must be greater than 0.",
          )}
        </FieldDescription>
        {authAccessTokenMinutesError ? (
          <FieldError id="gateway-auth-access-token-minutes-error">
            {authAccessTokenMinutesError}
          </FieldError>
        ) : null}
      </Field>
      <Field data-invalid={Boolean(requestTimeoutSecondsError)}>
        <FieldLabel htmlFor="gateway-request-timeout-seconds">
          {titleForLocale(
            locale,
            "请求超时（秒）",
            "Request timeout (seconds)",
          )}
        </FieldLabel>
        <Input
          id="gateway-request-timeout-seconds"
          type="number"
          required
          min="0"
          max="86400"
          step="any"
          value={requestTimeoutSeconds}
          aria-invalid={Boolean(requestTimeoutSecondsError)}
          aria-describedby={
            requestTimeoutSecondsError
              ? "gateway-request-timeout-seconds-description gateway-request-timeout-seconds-error"
              : "gateway-request-timeout-seconds-description"
          }
          onChange={(event) =>
            onRequestTimeoutSecondsChange(event.target.value)
          }
        />
        <FieldDescription id="gateway-request-timeout-seconds-description">
          {titleForLocale(
            locale,
            "限制单次网关请求（含回退）的总时长；设为 0 时不限制。",
            "Limits the total duration of a gateway request, including fallbacks; set to 0 for no limit.",
          )}
        </FieldDescription>
        {requestTimeoutSecondsError ? (
          <FieldError id="gateway-request-timeout-seconds-error">
            {requestTimeoutSecondsError}
          </FieldError>
        ) : null}
      </Field>
      <Field data-invalid={Boolean(maxRequestBodyBytesError)}>
        <FieldLabel htmlFor="gateway-max-request-body-bytes">
          {titleForLocale(
            locale,
            "最大请求体（字节）",
            "Maximum request body (bytes)",
          )}
        </FieldLabel>
        <Input
          id="gateway-max-request-body-bytes"
          type="number"
          required
          min="0"
          step="1"
          value={maxRequestBodyBytes}
          aria-invalid={Boolean(maxRequestBodyBytesError)}
          aria-describedby={
            maxRequestBodyBytesError
              ? "gateway-max-request-body-bytes-description gateway-max-request-body-bytes-error"
              : "gateway-max-request-body-bytes-description"
          }
          onChange={(event) => onMaxRequestBodyBytesChange(event.target.value)}
        />
        <FieldDescription id="gateway-max-request-body-bytes-description">
          {titleForLocale(
            locale,
            "限制发送到上游的请求体大小；设为 0 时不限制。",
            "Limits the size of the request body sent upstream; set to 0 for no limit.",
          )}
        </FieldDescription>
        {maxRequestBodyBytesError ? (
          <FieldError id="gateway-max-request-body-bytes-error">
            {maxRequestBodyBytesError}
          </FieldError>
        ) : null}
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
