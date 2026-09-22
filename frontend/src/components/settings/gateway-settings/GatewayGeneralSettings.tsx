import { Field, FieldError, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { Textarea } from "@/components/ui/Textarea";
import { titleForLocale } from "@/lib/I18nContext";
import { SettingsFieldList, SettingsFieldRow } from "../settingsLayout";
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
  onProxyUrlChange,
  onCorsAllowOriginsChange,
  onAuthAccessTokenMinutesChange,
  onFirstTokenTimeoutSecondsChange,
  onStreamIdleTimeoutSecondsChange,
  onMaxRequestBodyBytesChange,
  onRelayLogBodyEnabledChange,
}: GatewayGeneralSettingsProps) {
  return (
    <SettingsFieldList>
      <SettingsFieldRow
        title={titleForLocale(locale, "全局代理地址", "Global proxy URL")}
      >
        <Input
          className="w-full"
          value={proxyUrl}
          onChange={(event) => onProxyUrlChange(event.target.value)}
          placeholder="http://127.0.0.1:7890"
        />
      </SettingsFieldRow>
      <Field>
        <FieldLabel>
          {titleForLocale(locale, "CORS 跨域名单", "CORS allow origins")}
        </FieldLabel>
        <Textarea
          className="mt-2 min-h-[92px]"
          value={corsAllowOrigins}
          onChange={(event) => onCorsAllowOriginsChange(event.target.value)}
          placeholder={"*\nhttp://localhost:3000"}
        />
      </Field>
      <SettingsFieldRow
        htmlFor="gateway-auth-access-token-minutes"
        title={titleForLocale(
          locale,
          "访问令牌有效期（分钟）",
          "Access token lifetime (minutes)",
        )}
        invalid={Boolean(authAccessTokenMinutesError)}
      >
        <Input
          id="gateway-auth-access-token-minutes"
          className="w-full"
          type="number"
          required
          min="1"
          max="525600"
          step="1"
          value={authAccessTokenMinutes}
          aria-invalid={Boolean(authAccessTokenMinutesError)}
          onChange={(event) =>
            onAuthAccessTokenMinutesChange(event.target.value)
          }
        />
        {authAccessTokenMinutesError ? (
          <FieldError>{authAccessTokenMinutesError}</FieldError>
        ) : null}
      </SettingsFieldRow>
      <SettingsFieldRow
        htmlFor="gateway-first-token-timeout-seconds"
        title={titleForLocale(
          locale,
          "首字超时（秒）",
          "First-token timeout (seconds)",
        )}
        description={titleForLocale(
          locale,
          "限制首个可交付响应：流式请求须在预算内产生首个有效协议输出，非流式请求须在预算内读完完整响应；路由和回退共享该预算，设为 0 时不限制。",
          "Limits the first deliverable response: streaming requests must produce meaningful protocol output within the shared routing and fallback budget, while non-streaming requests must finish reading the full response; set to 0 for no limit.",
        )}
        invalid={Boolean(firstTokenTimeoutSecondsError)}
      >
        <Input
          id="gateway-first-token-timeout-seconds"
          className="w-full"
          type="number"
          required
          min="0"
          max="86400"
          step="any"
          value={firstTokenTimeoutSeconds}
          aria-invalid={Boolean(firstTokenTimeoutSecondsError)}
          onChange={(event) =>
            onFirstTokenTimeoutSecondsChange(event.target.value)
          }
        />
        {firstTokenTimeoutSecondsError ? (
          <FieldError>{firstTokenTimeoutSecondsError}</FieldError>
        ) : null}
      </SettingsFieldRow>
      <SettingsFieldRow
        htmlFor="gateway-stream-idle-timeout-seconds"
        title={titleForLocale(
          locale,
          "流空闲超时（秒）",
          "Stream idle timeout (seconds)",
        )}
        description={titleForLocale(
          locale,
          "首个有效输出之后，相邻上游数据块之间的最长滚动等待；设为 0 时禁用流空闲限制。",
          "Sets the rolling maximum wait between upstream chunks after the first meaningful output; set to 0 to disable this limit.",
        )}
        invalid={Boolean(streamIdleTimeoutSecondsError)}
      >
        <Input
          id="gateway-stream-idle-timeout-seconds"
          className="w-full"
          type="number"
          required
          min="0"
          max="86400"
          step="any"
          value={streamIdleTimeoutSeconds}
          aria-invalid={Boolean(streamIdleTimeoutSecondsError)}
          onChange={(event) =>
            onStreamIdleTimeoutSecondsChange(event.target.value)
          }
        />
        {streamIdleTimeoutSecondsError ? (
          <FieldError>{streamIdleTimeoutSecondsError}</FieldError>
        ) : null}
      </SettingsFieldRow>
      <SettingsFieldRow
        htmlFor="gateway-max-request-body-bytes"
        title={titleForLocale(
          locale,
          "最大请求体（字节）",
          "Maximum request body (bytes)",
        )}
        description={titleForLocale(
          locale,
          "限制发送到上游的请求体大小；设为 0 时不限制。",
          "Limits the size of the request body sent upstream; set to 0 for no limit.",
        )}
        invalid={Boolean(maxRequestBodyBytesError)}
      >
        <Input
          id="gateway-max-request-body-bytes"
          className="w-full"
          type="number"
          required
          min="0"
          step="1"
          value={maxRequestBodyBytes}
          aria-invalid={Boolean(maxRequestBodyBytesError)}
          onChange={(event) => onMaxRequestBodyBytesChange(event.target.value)}
        />
        {maxRequestBodyBytesError ? (
          <FieldError>{maxRequestBodyBytesError}</FieldError>
        ) : null}
      </SettingsFieldRow>
      <SettingsFieldRow
        title={titleForLocale(locale, "记录日志正文", "Record log body")}
      >
        <Switch
          checked={isRelayLogBodyEnabled}
          onCheckedChange={onRelayLogBodyEnabledChange}
        />
      </SettingsFieldRow>
    </SettingsFieldList>
  );
}
