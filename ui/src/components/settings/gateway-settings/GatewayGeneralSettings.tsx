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
  firstTokenTimeoutSeconds,
  streamIdleTimeoutSeconds,
  maxRequestBodyBytes,
  authAccessTokenMinutesError,
  firstTokenTimeoutSecondsError,
  streamIdleTimeoutSecondsError,
  maxRequestBodyBytesError,
  isRelayLogBodyEnabled,
  isModelListCompatModeEnabled,
  onProxyUrlChange,
  onCorsAllowOriginsChange,
  onAuthAccessTokenMinutesChange,
  onFirstTokenTimeoutSecondsChange,
  onStreamIdleTimeoutSecondsChange,
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
      <Field data-invalid={Boolean(firstTokenTimeoutSecondsError)}>
        <FieldLabel htmlFor="gateway-first-token-timeout-seconds">
          {titleForLocale(
            locale,
            "首字超时（秒）",
            "First-token timeout (seconds)",
          )}
        </FieldLabel>
        <Input
          id="gateway-first-token-timeout-seconds"
          type="number"
          required
          min="0"
          max="86400"
          step="any"
          value={firstTokenTimeoutSeconds}
          aria-invalid={Boolean(firstTokenTimeoutSecondsError)}
          aria-describedby={
            firstTokenTimeoutSecondsError
              ? "gateway-first-token-timeout-seconds-description gateway-first-token-timeout-seconds-error"
              : "gateway-first-token-timeout-seconds-description"
          }
          onChange={(event) =>
            onFirstTokenTimeoutSecondsChange(event.target.value)
          }
        />
        <FieldDescription id="gateway-first-token-timeout-seconds-description">
          {titleForLocale(
            locale,
            "限制首个可交付响应：流式请求须在预算内产生首个有效协议输出，非流式请求须在预算内读完完整响应；路由和回退共享该预算，设为 0 时不限制。",
            "Limits the first deliverable response: streaming requests must produce meaningful protocol output within the shared routing and fallback budget, while non-streaming requests must finish reading the full response; set to 0 for no limit.",
          )}
        </FieldDescription>
        {firstTokenTimeoutSecondsError ? (
          <FieldError id="gateway-first-token-timeout-seconds-error">
            {firstTokenTimeoutSecondsError}
          </FieldError>
        ) : null}
      </Field>
      <Field data-invalid={Boolean(streamIdleTimeoutSecondsError)}>
        <FieldLabel htmlFor="gateway-stream-idle-timeout-seconds">
          {titleForLocale(
            locale,
            "流空闲超时（秒）",
            "Stream idle timeout (seconds)",
          )}
        </FieldLabel>
        <Input
          id="gateway-stream-idle-timeout-seconds"
          type="number"
          required
          min="0"
          max="86400"
          step="any"
          value={streamIdleTimeoutSeconds}
          aria-invalid={Boolean(streamIdleTimeoutSecondsError)}
          aria-describedby={
            streamIdleTimeoutSecondsError
              ? "gateway-stream-idle-timeout-seconds-description gateway-stream-idle-timeout-seconds-error"
              : "gateway-stream-idle-timeout-seconds-description"
          }
          onChange={(event) =>
            onStreamIdleTimeoutSecondsChange(event.target.value)
          }
        />
        <FieldDescription id="gateway-stream-idle-timeout-seconds-description">
          {titleForLocale(
            locale,
            "首个有效输出之后，相邻上游数据块之间的最长滚动等待；设为 0 时禁用流空闲限制。",
            "Sets the rolling maximum wait between upstream chunks after the first meaningful output; set to 0 to disable this limit.",
          )}
        </FieldDescription>
        {streamIdleTimeoutSecondsError ? (
          <FieldError id="gateway-stream-idle-timeout-seconds-error">
            {streamIdleTimeoutSecondsError}
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
