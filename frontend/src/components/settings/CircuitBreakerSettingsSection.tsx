import { FieldError } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { TabsContent } from "@/components/ui/Tabs";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import { SettingsSectionCard } from "./SettingsSectionCard";
import {
  SettingsFieldList,
  SettingsFieldRow,
  SettingsSectionSeparator,
} from "./settingsLayout";
import type { useSettingsDraft } from "./useSettingsDraft";

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
  | "failoverCooledWaitSeconds"
  | "circuitBreakerEscalateThreshold"
  | "circuitBreakerEscalateWindowSeconds"
  | "failoverAffinitySeconds"
  | "healthWindowSeconds"
  | "healthPenaltyWeight"
  | "healthMinSamples";

interface CircuitBreakerFieldDefinition {
  key: CircuitBreakerKey;
  id: string;
  label: string;
  description?: string;
  min: string;
  max?: string;
  step?: string;
}

interface CircuitBreakerFieldGroup {
  title: string;
  showHealthToggle?: boolean;
  fields: ReadonlyArray<CircuitBreakerFieldDefinition>;
}

type SettingsDraftController = ReturnType<typeof useSettingsDraft>;

const HEALTH_SCORING_TOGGLE_ID = "settings-health-scoring-enabled";
interface NumberSettingFieldProps {
  id: string;
  label: string;
  description?: string;
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
  const errorId = `${id}-error`;

  return (
    <SettingsFieldRow
      htmlFor={id}
      title={label}
      description={description}
      invalid={Boolean(error)}
    >
      <Input
        id={id}
        className="w-full"
        type="number"
        required
        min={min}
        max={max}
        step={step}
        value={value}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? <FieldError id={errorId}>{error}</FieldError> : null}
    </SettingsFieldRow>
  );
}

function _getCircuitBreakerFieldGroups(
  locale: Locale,
): ReadonlyArray<CircuitBreakerFieldGroup> {
  return [
    {
      title: titleForLocale(locale, "失败阈值", "Failure thresholds"),
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
            "同一模型连续 5xx 的触发次数；带 Retry-After 的 503 立即冷却。",
            "Consecutive 5xx responses for one model; 503 with Retry-After cools immediately.",
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
            "冷却恢复后，无新失败超过该时长才重置计数和退避。",
            "After cooldown, reset counts and backoff after this long without a new failure.",
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
          min: "1",
        },
      ],
    },
    {
      title: titleForLocale(locale, "分类初始冷却", "Initial cooldowns"),
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
            "只冷却失败的 Key。",
            "Cools only the failed key.",
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
            "无法确认更大故障范围时，只冷却当前模型。",
            "Cools only the current model when a wider fault is unproven.",
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
          min: "0",
          max: "604800",
        },
      ],
    },
    {
      title: titleForLocale(locale, "冷却退避", "Cooldown backoff"),
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
            "重复冷却时的倍率（1–10）。",
            "Multiplier for repeated cooldowns (1–10).",
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
            "所有冷却和退避的上限；0 关闭自动冷却。",
            "Cap for cooldowns and backoff; 0 disables automatic cooldown.",
          ),
          min: "0",
          max: "604800",
        },
        {
          key: "failoverCooledWaitSeconds",
          id: "settings-failover-cooled-wait-seconds",
          label: titleForLocale(
            locale,
            "故障转移等待上限（秒）",
            "Failover wait cap (seconds)",
          ),
          description: titleForLocale(
            locale,
            "候选都冷却时的最长等待；0 立即返回。",
            "Max wait when all candidates cool; 0 returns immediately.",
          ),
          min: "0",
          max: "604800",
        },
        {
          key: "circuitBreakerEscalateThreshold",
          id: "settings-circuit-breaker-escalate-threshold",
          label: titleForLocale(
            locale,
            "限流升级 Key 数",
            "Rate-limit escalation key count",
          ),
          description: titleForLocale(
            locale,
            "窗口内达到该 Key 数后升级为模型冷却；0 关闭。",
            "Escalate to model cooldown at this key count; 0 disables.",
          ),
          min: "0",
          max: "100",
        },
        {
          key: "circuitBreakerEscalateWindowSeconds",
          id: "settings-circuit-breaker-escalate-window",
          label: titleForLocale(
            locale,
            "限流升级窗口（秒）",
            "Rate-limit escalation window (seconds)",
          ),
          min: "0",
          max: "604800",
        },
        {
          key: "failoverAffinitySeconds",
          id: "settings-failover-affinity-seconds",
          label: titleForLocale(
            locale,
            "故障切换亲和窗口（秒）",
            "Failover affinity window (seconds)",
          ),
          description: titleForLocale(
            locale,
            "故障切换成功后的优先使用时长；0 关闭。",
            "Prefer the successful failover target for this long; 0 disables.",
          ),
          min: "0",
          max: "3600",
        },
      ],
    },
    {
      title: titleForLocale(
        locale,
        "健康排序参数",
        "Health ranking parameters",
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
            "近期失败率的排序影响（0–1）。",
            "Recent failure impact on ranking (0–1).",
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
            "达到该样本数后使用完整惩罚。",
            "Full penalty starts at this sample count.",
          ),
          min: "1",
        },
      ],
    },
  ];
}

/** Render circuit breaker and health scoring settings. */

export function CircuitBreakerSettingsSection({
  locale,
  settings,
}: {
  locale: Locale;
  settings: SettingsDraftController;
}) {
  return (
    <TabsContent value="circuit-breaker" className="mt-0">
      <SettingsSectionCard
        title={titleForLocale(locale, "故障转移", "Failover")}
      >
        {_getCircuitBreakerFieldGroups(locale).map((group, groupIndex) => (
          <div key={group.title}>
            {groupIndex > 0 ? <SettingsSectionSeparator /> : null}
            <h4 className="mb-4 text-sm font-semibold">{group.title}</h4>
            <SettingsFieldList>
              {group.showHealthToggle ? (
                <SettingsFieldRow
                  htmlFor={HEALTH_SCORING_TOGGLE_ID}
                  title={titleForLocale(
                    locale,
                    "按健康度排序",
                    "Sort by health",
                  )}
                  description={titleForLocale(
                    locale,
                    "关闭后按原始顺序或轮询。",
                    "Off: use configured order or round robin.",
                  )}
                >
                  <Switch
                    id={HEALTH_SCORING_TOGGLE_ID}
                    checked={settings.draft.isHealthScoringEnabled}
                    onCheckedChange={(checked) =>
                      settings.setDraftValue("isHealthScoringEnabled", checked)
                    }
                  />
                </SettingsFieldRow>
              ) : null}
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
                  onChange={(value) => settings.setDraftValue(field.key, value)}
                />
              ))}
            </SettingsFieldList>
          </div>
        ))}
      </SettingsSectionCard>
    </TabsContent>
  );
}
