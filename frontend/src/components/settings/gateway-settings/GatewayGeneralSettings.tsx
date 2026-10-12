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
        title={titleForLocale(locale, "上游代理", "Upstream proxy")}
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
          {titleForLocale(
            locale,
            "跨域资源共享 (CORS) 允许源",
            "Allowed CORS Origins",
          )}
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
          "管理员登录有效期（分钟）",
          "Admin session lifetime (minutes)",
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
          "首个 Token 超时（秒）",
          "First token timeout (seconds)",
        )}
        description={titleForLocale(
          locale,
          "限定产生首个有效数据块的最长等待时间。流式与非流式请求在全部故障切换尝试中共用此预算；设为 0 表示不设上限。",
          "Sets maximum wait for initial meaningful protocol response, shared across all failover attempts. 0 means unlimited.",
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
          "流式响应空闲超时（秒）",
          "Stream idle timeout (seconds)",
        )}
        description={titleForLocale(
          locale,
          "首字输出后，相邻数据块之间的最长静默间隔。若上游停滞超过此时长将主动中断；设为 0 则不限制。",
          "Maximum silence permitted between stream chunks after first token. 0 disables limit.",
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
          "请求体大小上限（字节）",
          "Request body limit (bytes)",
        )}
        description={titleForLocale(
          locale,
          "限制客户端单次提交的最大载荷大小（针对大图像或长上下文请求）；设为 0 表示不限制。",
          "Limits client request body size (e.g. large images or long contexts). 0 means unlimited.",
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
        title={titleForLocale(locale, "记录请求正文", "Record request bodies")}
      >
        <Switch
          checked={isRelayLogBodyEnabled}
          onCheckedChange={onRelayLogBodyEnabledChange}
        />
      </SettingsFieldRow>
    </SettingsFieldList>
  );
}
