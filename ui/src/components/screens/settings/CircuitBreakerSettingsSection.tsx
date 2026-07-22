import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { TabsContent } from "@/components/ui/Tabs";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import { SettingsSectionCard } from "./SettingsSectionCard";
import { type useSettingsDraft } from "./useSettingsDraft";

type CircuitBreakerKey =
  | "circuitBreakerThreshold"
  | "circuitBreakerFailureWindowSeconds"
  | "circuitBreakerTimeoutThreshold"
  | "circuitBreakerNetworkThreshold"
  | "circuitBreakerCooldown"
  | "circuitBreakerAuthCooldown"
  | "circuitBreakerNotFoundCooldown"
  | "circuitBreakerRateLimitCooldown"
  | "circuitBreakerTimeoutCooldown"
  | "circuitBreakerNetworkCooldown"
  | "circuitBreakerBackoffMultiplier"
  | "circuitBreakerMaxCooldown"
  | "healthWindowSeconds"
  | "healthPenaltyWeight"
  | "healthMinSamples";

interface CircuitBreakerFieldDefinition {
  key: CircuitBreakerKey;
  id: string;
  label: string;
  description: string;
  min: string;
  max?: string;
  step?: string;
}

interface CircuitBreakerFieldGroup {
  title: string;
  description: string;
  showHealthToggle?: boolean;
  fields: ReadonlyArray<CircuitBreakerFieldDefinition>;
}

type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

const HEALTH_SCORING_TOGGLE_ID = "settings-health-scoring-enabled";
const HEALTH_SCORING_DESCRIPTION_ID = `${HEALTH_SCORING_TOGGLE_ID}-description`;

interface NumberSettingFieldProps {
  id: string;
  label: string;
  description: string;
  min: string;
  max?: string;
  step?: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}

function NumberSettingField({
  id,
  label,
  description,
  min,
  max,
  step,
  value,
  error,
  onChange,
}: NumberSettingFieldProps) {
  const descriptionId = `${id}-description`;
  const errorId = `${id}-error`;

  return (
    <Field data-invalid={Boolean(error)}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        type="number"
        required
        min={min}
        max={max}
        step={step}
        value={value}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${descriptionId} ${errorId}` : descriptionId}
        onChange={(event) => onChange(event.target.value)}
      />
      <FieldDescription id={descriptionId}>{description}</FieldDescription>
      {error ? <FieldError id={errorId}>{error}</FieldError> : null}
    </Field>
  );
}

function _getCircuitBreakerFieldGroups(
  locale: Locale,
): ReadonlyArray<CircuitBreakerFieldGroup> {
  return [
    {
      title: titleForLocale(locale, "失败阈值", "Failure thresholds"),
      description: titleForLocale(
        locale,
        "连续失败按实际模型分别累计，达到对应阈值后才冷却该模型。",
        "Consecutive failures are counted per actual model before that model enters cooldown.",
      ),
      fields: [
        {
          key: "circuitBreakerThreshold",
          id: "settings-circuit-breaker-threshold",
          label: titleForLocale(
            locale,
            "5xx 失败阈值",
            "5xx failure threshold",
          ),
          description: titleForLocale(
            locale,
            "同一实际模型连续发生上游 5xx 的触发次数；503 明确提供 Retry-After 时立即冷却。",
            "Consecutive upstream 5xx responses required for the same actual model; a 503 with Retry-After triggers cooldown immediately.",
          ),
          min: "1",
        },
        {
          key: "circuitBreakerFailureWindowSeconds",
          id: "settings-circuit-breaker-failure-window",
          label: titleForLocale(
            locale,
            "连续失败窗口（秒）",
            "Consecutive-failure window (seconds)",
          ),
          description: titleForLocale(
            locale,
            "未进入冷却时按相邻失败间隔计算；冷却结束后持续无新失败超过该时间，连续失败计数和退避历史才重新开始。",
            "Before cooldown this measures the gap between failures; after recovery, failure counts and backoff restart only after this much time without another failure.",
          ),
          min: "1",
          max: "604800",
        },
        {
          key: "circuitBreakerTimeoutThreshold",
          id: "settings-circuit-breaker-timeout-threshold",
          label: titleForLocale(
            locale,
            "超时失败阈值",
            "Timeout failure threshold",
          ),
          description: titleForLocale(
            locale,
            "同一实际模型连续发生上游超时的触发次数。",
            "Consecutive upstream timeouts required for the same actual model.",
          ),
          min: "1",
        },
        {
          key: "circuitBreakerNetworkThreshold",
          id: "settings-circuit-breaker-network-threshold",
          label: titleForLocale(
            locale,
            "网络失败阈值",
            "Network failure threshold",
          ),
          description: titleForLocale(
            locale,
            "同一实际模型连续发生连接或网络错误的触发次数。",
            "Consecutive connection or network errors required for the same actual model.",
          ),
          min: "1",
        },
      ],
    },
    {
      title: titleForLocale(locale, "分类初始冷却", "Initial cooldowns"),
      description: titleForLocale(
        locale,
        "模型错误先冷却实际模型，认证错误只冷却对应 Key；没有任何启用的 Key + 模型绑定可用时，渠道才整体不可用。初始冷却设为 0 可关闭对应类别。",
        "Model errors first cool the actual model, while authentication errors cool only the affected key; the channel becomes unavailable only when no enabled key-model binding remains available. Set an initial cooldown to 0 to disable that category.",
      ),
      fields: [
        {
          key: "circuitBreakerAuthCooldown",
          id: "settings-circuit-breaker-auth-cooldown",
          label: titleForLocale(
            locale,
            "认证错误初始冷却（秒）",
            "Authentication initial cooldown (seconds)",
          ),
          description: titleForLocale(
            locale,
            "认证失败时冷却对应 Key，不影响其他启用 Key。",
            "Cooldown for the rejected key without blocking other enabled keys.",
          ),
          min: "0",
          max: "604800",
        },
        {
          key: "circuitBreakerNotFoundCooldown",
          id: "settings-circuit-breaker-not-found-cooldown",
          label: titleForLocale(
            locale,
            "404 初始冷却（秒）",
            "404 initial cooldown (seconds)",
          ),
          description: titleForLocale(
            locale,
            "无法从响应内容确认故障范围时，404 保守地只冷却当前实际模型。",
            "When the response does not prove a broader fault, a 404 conservatively cools only the current actual model.",
          ),
          min: "0",
          max: "604800",
        },
        {
          key: "circuitBreakerRateLimitCooldown",
          id: "settings-circuit-breaker-rate-limit-cooldown",
          label: titleForLocale(
            locale,
            "限流初始冷却（秒）",
            "Rate-limit initial cooldown (seconds)",
          ),
          description: titleForLocale(
            locale,
            "上游限流当前实际模型时使用。",
            "Applied when the upstream rate-limits the current actual model.",
          ),
          min: "0",
          max: "604800",
        },
        {
          key: "circuitBreakerCooldown",
          id: "settings-circuit-breaker-cooldown",
          label: titleForLocale(
            locale,
            "5xx 初始冷却（秒）",
            "5xx initial cooldown (seconds)",
          ),
          description: titleForLocale(
            locale,
            "上游 5xx 达到失败阈值后使用。",
            "Applied after upstream 5xx responses reach the failure threshold.",
          ),
          min: "0",
          max: "604800",
        },
        {
          key: "circuitBreakerTimeoutCooldown",
          id: "settings-circuit-breaker-timeout-cooldown",
          label: titleForLocale(
            locale,
            "超时初始冷却（秒）",
            "Timeout initial cooldown (seconds)",
          ),
          description: titleForLocale(
            locale,
            "上游超时达到失败阈值后使用。",
            "Applied after upstream timeouts reach the failure threshold.",
          ),
          min: "0",
          max: "604800",
        },
        {
          key: "circuitBreakerNetworkCooldown",
          id: "settings-circuit-breaker-network-cooldown",
          label: titleForLocale(
            locale,
            "网络错误初始冷却（秒）",
            "Network initial cooldown (seconds)",
          ),
          description: titleForLocale(
            locale,
            "连接或网络错误达到失败阈值后使用。",
            "Applied after connection or network errors reach the failure threshold.",
          ),
          min: "0",
          max: "604800",
        },
      ],
    },
    {
      title: titleForLocale(locale, "冷却退避", "Cooldown backoff"),
      description: titleForLocale(
        locale,
        "同一模型或 Key 反复失败时延长冷却，但始终受最大冷却限制。",
        "Repeated failures extend cooldown for the same model or key, bounded by the maximum cooldown.",
      ),
      fields: [
        {
          key: "circuitBreakerBackoffMultiplier",
          id: "settings-circuit-breaker-backoff-multiplier",
          label: titleForLocale(
            locale,
            "冷却退避倍率",
            "Cooldown backoff multiplier",
          ),
          description: titleForLocale(
            locale,
            "同一模型或 Key 重复进入冷却时应用的倍率，范围为 1 到 10。",
            "Multiplier applied when the same model or key re-enters cooldown, from 1 to 10.",
          ),
          min: "1",
          max: "10",
          step: "any",
        },
        {
          key: "circuitBreakerMaxCooldown",
          id: "settings-circuit-breaker-max-cooldown",
          label: titleForLocale(
            locale,
            "最大冷却（秒）",
            "Maximum cooldown (seconds)",
          ),
          description: titleForLocale(
            locale,
            "所有分类冷却和自动退避的硬上限；设为 0 会关闭全部自动冷却。",
            "Hard upper bound for every cooldown category and automatic backoff; set to 0 to disable all automatic cooldown.",
          ),
          min: "0",
          max: "604800",
        },
      ],
    },
    {
      title: titleForLocale(
        locale,
        "健康排序参数",
        "Health ranking parameters",
      ),
      description: titleForLocale(
        locale,
        "冷却过滤之后，轮询策略按近期健康分分配流量；故障切换策略仍保持配置顺序。",
        "After cooldown filtering, round-robin traffic is weighted by recent health while failover preserves configured order.",
      ),
      showHealthToggle: true,
      fields: [
        {
          key: "healthWindowSeconds",
          id: "settings-health-window-seconds",
          label: titleForLocale(
            locale,
            "健康窗口（秒）",
            "Health window (seconds)",
          ),
          description: titleForLocale(
            locale,
            "健康评分统计近期请求结果的时间范围。",
            "Time range of recent request outcomes used for health scoring.",
          ),
          min: "1",
          max: "604800",
        },
        {
          key: "healthPenaltyWeight",
          id: "settings-health-penalty-weight",
          label: titleForLocale(
            locale,
            "健康惩罚权重",
            "Health penalty weight",
          ),
          description: titleForLocale(
            locale,
            "控制近期失败率对排序的影响，范围为 0 到 1。",
            "Controls how strongly recent failures affect ranking, from 0 to 1.",
          ),
          min: "0",
          max: "1",
          step: "any",
        },
        {
          key: "healthMinSamples",
          id: "settings-health-min-samples",
          label: titleForLocale(
            locale,
            "完整置信样本数",
            "Full-confidence sample count",
          ),
          description: titleForLocale(
            locale,
            "达到该样本数后使用完整失败率惩罚；样本较少时影响会减弱。",
            "The full failure-rate penalty applies at this sample count; smaller samples have less influence.",
          ),
          min: "1",
        },
      ],
    },
  ];
}

/** Render circuit breaker and health scoring settings. */
export function CircuitBreakerSettingsSection({
  description,
  locale,
  settings,
}: {
  description: string;
  locale: Locale;
  settings: SettingsDraftController;
}) {
  return (
    <TabsContent value="circuit-breaker" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(
          locale,
          "冷却与健康排序",
          "Cooldown and health ranking",
        )}
        description={description}
      >
        <FieldGroup>
          {_getCircuitBreakerFieldGroups(locale).map((group) => (
            <section key={group.title} className="flex flex-col gap-3">
              <div>
                <h3 className="text-sm font-medium text-foreground">
                  {group.title}
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {group.description}
                </p>
              </div>

              {group.showHealthToggle ? (
                <Field
                  orientation="horizontal"
                  className="items-center justify-between gap-4 rounded-lg border p-3"
                >
                  <FieldContent>
                    <FieldLabel
                      htmlFor={HEALTH_SCORING_TOGGLE_ID}
                      className="w-auto"
                    >
                      {titleForLocale(
                        locale,
                        "启用健康排序",
                        "Enable health ranking",
                      )}
                    </FieldLabel>
                    <FieldDescription id={HEALTH_SCORING_DESCRIPTION_ID}>
                      {titleForLocale(
                        locale,
                        "关闭后仅按所选路由策略的原始顺序或等权轮询选择可用模型。",
                        "When disabled, available models use the configured order or equal-weight round robin for the selected strategy.",
                      )}
                    </FieldDescription>
                  </FieldContent>
                  <Switch
                    id={HEALTH_SCORING_TOGGLE_ID}
                    aria-describedby={HEALTH_SCORING_DESCRIPTION_ID}
                    checked={settings.draft.isHealthScoringEnabled}
                    onCheckedChange={(checked) =>
                      settings.setDraftValue("isHealthScoringEnabled", checked)
                    }
                  />
                </Field>
              ) : null}

              <div className="grid gap-4 sm:grid-cols-2">
                {group.fields.map((field) => (
                  <NumberSettingField
                    key={field.key}
                    id={field.id}
                    label={field.label}
                    description={field.description}
                    min={field.min}
                    max={field.max}
                    step={field.step}
                    value={settings.draft[field.key]}
                    error={settings.numericSettingErrors[field.key]}
                    onChange={(value) =>
                      settings.setDraftValue(field.key, value)
                    }
                  />
                ))}
              </div>
            </section>
          ))}
        </FieldGroup>
      </SettingsSectionCard>
    </TabsContent>
  );
}
