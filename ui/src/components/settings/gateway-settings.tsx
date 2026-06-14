"use client";

import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { titleForLocale, useI18n, type Locale } from "@/lib/i18n";
import {
  type ParamOverrideMatchType,
  type UpstreamParamOverrideDraft,
  type UpstreamParamOverrideRuleDraft,
} from "@/lib/settings-types";

type HeaderItem = { key: string; value: string };
type UpstreamHeaderMatchType = "exact" | "regex";
type UpstreamHeaderRuleDraft = {
  id: string;
  enabled: boolean;
  name: string;
  matchType: UpstreamHeaderMatchType;
  models: string;
  pattern: string;
  headers: HeaderItem[];
};
type UpstreamHeadersDraft = {
  global: HeaderItem[];
  rules: UpstreamHeaderRuleDraft[];
};

interface GatewaySettingsProps {
  proxyUrl: string;
  corsAllowOrigins: string;
  relayLogBodyEnabled: boolean;
  modelListCompatModeEnabled: boolean;
  upstreamHeadersConfig: UpstreamHeadersDraft;
  upstreamParamOverrideConfig: UpstreamParamOverrideDraft;
  onProxyUrlChange: (value: string) => void;
  onCorsAllowOriginsChange: (value: string) => void;
  onRelayLogBodyEnabledChange: (checked: boolean) => void;
  onModelListCompatModeEnabledChange: (checked: boolean) => void;
  onAddGlobalHeader: () => void;
  onUpdateGlobalHeader: (index: number, patch: Partial<HeaderItem>) => void;
  onRemoveGlobalHeader: (index: number) => void;
  onAddRule: () => void;
  onUpdateRule: (
    index: number,
    patch: Partial<UpstreamHeaderRuleDraft>,
  ) => void;
  onRemoveRule: (index: number) => void;
  onMoveRule: (index: number, direction: -1 | 1) => void;
  onAddRuleHeader: (ruleIndex: number) => void;
  onUpdateRuleHeader: (
    ruleIndex: number,
    headerIndex: number,
    patch: Partial<HeaderItem>,
  ) => void;
  onRemoveRuleHeader: (ruleIndex: number, headerIndex: number) => void;
  onGlobalParamOverrideChange: (value: string) => void;
  onAddParamOverrideRule: () => void;
  onUpdateParamOverrideRule: (
    index: number,
    patch: Partial<UpstreamParamOverrideRuleDraft>,
  ) => void;
  onRemoveParamOverrideRule: (index: number) => void;
  onMoveParamOverrideRule: (index: number, direction: -1 | 1) => void;
}

function HeaderRows({
  title,
  headers,
  locale,
  onAdd,
  onUpdate,
  onRemove,
}: {
  title: string;
  headers: HeaderItem[];
  locale: Locale;
  onAdd: () => void;
  onUpdate: (index: number, patch: Partial<HeaderItem>) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          <Plus data-icon="inline-start" />
          {titleForLocale(locale, "添加", "Add")}
        </Button>
      </div>
      {headers.map((header, headerIndex) => (
        <div
          key={headerIndex}
          className="grid gap-3 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
        >
          <Field>
            <FieldLabel>
              {titleForLocale(locale, "请求头名称", "Header key")}
            </FieldLabel>
            <Input
              value={header.key}
              onChange={(event) =>
                onUpdate(headerIndex, { key: event.target.value })
              }
              placeholder="X-Header-Name"
            />
          </Field>
          <Field>
            <FieldLabel>
              {titleForLocale(locale, "请求头值", "Header value")}
            </FieldLabel>
            <Input
              value={header.value}
              onChange={(event) =>
                onUpdate(headerIndex, { value: event.target.value })
              }
              placeholder="value"
            />
          </Field>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="text-muted-foreground"
            aria-label={titleForLocale(locale, "删除请求头", "Remove header")}
            onClick={() => onRemove(headerIndex)}
          >
            <Trash2 data-icon="inline-start" />
          </Button>
        </div>
      ))}
    </div>
  );
}

export function GatewaySettings({
  proxyUrl,
  corsAllowOrigins,
  relayLogBodyEnabled,
  modelListCompatModeEnabled,
  upstreamHeadersConfig,
  upstreamParamOverrideConfig,
  onProxyUrlChange,
  onCorsAllowOriginsChange,
  onRelayLogBodyEnabledChange,
  onModelListCompatModeEnabledChange,
  onAddGlobalHeader,
  onUpdateGlobalHeader,
  onRemoveGlobalHeader,
  onAddRule,
  onUpdateRule,
  onRemoveRule,
  onMoveRule,
  onAddRuleHeader,
  onUpdateRuleHeader,
  onRemoveRuleHeader,
  onGlobalParamOverrideChange,
  onAddParamOverrideRule,
  onUpdateParamOverrideRule,
  onRemoveParamOverrideRule,
  onMoveParamOverrideRule,
}: GatewaySettingsProps) {
  const { locale } = useI18n();

  return (
    <FieldGroup>
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
          checked={modelListCompatModeEnabled}
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
          checked={relayLogBodyEnabled}
          onCheckedChange={onRelayLogBodyEnabledChange}
        />
      </Field>
      <div className="flex flex-col gap-5 rounded-lg border bg-muted/20 p-4">
        <HeaderRows
          title={titleForLocale(locale, "全局请求头", "Global headers")}
          headers={upstreamHeadersConfig.global}
          locale={locale}
          onAdd={onAddGlobalHeader}
          onUpdate={onUpdateGlobalHeader}
          onRemove={onRemoveGlobalHeader}
        />
        <Separator />
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-medium text-foreground">
            {titleForLocale(locale, "模型请求头规则", "Model header rules")}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={onAddRule}>
            <Plus data-icon="inline-start" />
            {titleForLocale(locale, "添加规则", "Add rule")}
          </Button>
        </div>
        {upstreamHeadersConfig.rules.length ? (
          <div className="flex flex-col gap-4">
            {upstreamHeadersConfig.rules.map((rule, ruleIndex) => (
              <div
                key={rule.id}
                className="flex flex-col gap-4 rounded-lg border bg-background p-3"
              >
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-end">
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "规则名称", "Rule name")}
                    </FieldLabel>
                    <Input
                      value={rule.name}
                      onChange={(event) =>
                        onUpdateRule(ruleIndex, { name: event.target.value })
                      }
                      placeholder={titleForLocale(
                        locale,
                        "规则名称",
                        "Rule name",
                      )}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "匹配方式", "Match type")}
                    </FieldLabel>
                    <SegmentedControl<UpstreamHeaderMatchType>
                      value={rule.matchType}
                      onValueChange={(matchType) =>
                        onUpdateRule(ruleIndex, { matchType })
                      }
                      options={[
                        {
                          value: "exact",
                          label: titleForLocale(locale, "精确", "Exact"),
                        },
                        {
                          value: "regex",
                          label: titleForLocale(locale, "正则", "Regex"),
                        },
                      ]}
                    />
                  </Field>
                  <div className="flex items-center justify-between gap-2 lg:justify-end">
                    <Switch
                      checked={rule.enabled}
                      aria-label={titleForLocale(
                        locale,
                        "启用规则",
                        "Enable rule",
                      )}
                      onCheckedChange={(enabled) =>
                        onUpdateRule(ruleIndex, { enabled })
                      }
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      aria-label={titleForLocale(
                        locale,
                        "上移规则",
                        "Move rule up",
                      )}
                      disabled={ruleIndex === 0}
                      onClick={() => onMoveRule(ruleIndex, -1)}
                    >
                      <ArrowUp data-icon="inline-start" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      aria-label={titleForLocale(
                        locale,
                        "下移规则",
                        "Move rule down",
                      )}
                      disabled={
                        ruleIndex === upstreamHeadersConfig.rules.length - 1
                      }
                      onClick={() => onMoveRule(ruleIndex, 1)}
                    >
                      <ArrowDown data-icon="inline-start" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="text-muted-foreground"
                      aria-label={titleForLocale(
                        locale,
                        "删除规则",
                        "Remove rule",
                      )}
                      onClick={() => onRemoveRule(ruleIndex)}
                    >
                      <Trash2 data-icon="inline-start" />
                    </Button>
                  </div>
                </div>
                {rule.matchType === "exact" ? (
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "模型名称", "Models")}
                    </FieldLabel>
                    <Textarea
                      className="min-h-[84px]"
                      value={rule.models}
                      onChange={(event) =>
                        onUpdateRule(ruleIndex, { models: event.target.value })
                      }
                      placeholder={"gpt-5.5\ngpt-5.4-mini"}
                    />
                  </Field>
                ) : (
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "模型正则", "Model regex")}
                    </FieldLabel>
                    <Input
                      value={rule.pattern}
                      onChange={(event) =>
                        onUpdateRule(ruleIndex, { pattern: event.target.value })
                      }
                      placeholder="^claude-"
                    />
                  </Field>
                )}
                <HeaderRows
                  title={titleForLocale(locale, "规则请求头", "Rule headers")}
                  headers={rule.headers}
                  locale={locale}
                  onAdd={() => onAddRuleHeader(ruleIndex)}
                  onUpdate={(headerIndex, patch) =>
                    onUpdateRuleHeader(ruleIndex, headerIndex, patch)
                  }
                  onRemove={(headerIndex) =>
                    onRemoveRuleHeader(ruleIndex, headerIndex)
                  }
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">
            {titleForLocale(locale, "暂无规则", "No rules")}
          </div>
        )}
      </div>
      <div className="flex flex-col gap-5 rounded-lg border bg-muted/20 p-4">
        <Field>
          <FieldLabel>
            {titleForLocale(locale, "全局参数覆盖", "Global param override")}
          </FieldLabel>
          <Textarea
            className="min-h-[92px] font-mono text-sm"
            value={upstreamParamOverrideConfig.global}
            onChange={(event) =>
              onGlobalParamOverrideChange(event.target.value)
            }
            placeholder={'{\n  "stream_options": { "include_usage": true }\n}'}
          />
          <FieldDescription>
            {titleForLocale(
              locale,
              "JSON 对象，深合并进所有协议的上游请求体；不可覆盖 model。",
              "JSON object, deep-merged into all protocols' upstream body; cannot override model.",
            )}
          </FieldDescription>
        </Field>
        <Separator />
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-medium text-foreground">
            {titleForLocale(
              locale,
              "模型参数覆盖规则",
              "Model param override rules",
            )}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onAddParamOverrideRule}
          >
            <Plus data-icon="inline-start" />
            {titleForLocale(locale, "添加规则", "Add rule")}
          </Button>
        </div>
        {upstreamParamOverrideConfig.rules.length ? (
          <div className="flex flex-col gap-4">
            {upstreamParamOverrideConfig.rules.map((rule, ruleIndex) => (
              <div
                key={rule.id}
                className="flex flex-col gap-4 rounded-lg border bg-background p-3"
              >
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-end">
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "规则名称", "Rule name")}
                    </FieldLabel>
                    <Input
                      value={rule.name}
                      onChange={(event) =>
                        onUpdateParamOverrideRule(ruleIndex, {
                          name: event.target.value,
                        })
                      }
                      placeholder={titleForLocale(
                        locale,
                        "规则名称",
                        "Rule name",
                      )}
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "匹配方式", "Match type")}
                    </FieldLabel>
                    <SegmentedControl<ParamOverrideMatchType>
                      value={rule.matchType}
                      onValueChange={(matchType) =>
                        onUpdateParamOverrideRule(ruleIndex, { matchType })
                      }
                      options={[
                        {
                          value: "exact",
                          label: titleForLocale(locale, "精确", "Exact"),
                        },
                        {
                          value: "regex",
                          label: titleForLocale(locale, "正则", "Regex"),
                        },
                      ]}
                    />
                  </Field>
                  <div className="flex items-center justify-between gap-2 lg:justify-end">
                    <Switch
                      checked={rule.enabled}
                      aria-label={titleForLocale(
                        locale,
                        "启用规则",
                        "Enable rule",
                      )}
                      onCheckedChange={(enabled) =>
                        onUpdateParamOverrideRule(ruleIndex, { enabled })
                      }
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      aria-label={titleForLocale(
                        locale,
                        "上移规则",
                        "Move rule up",
                      )}
                      disabled={ruleIndex === 0}
                      onClick={() => onMoveParamOverrideRule(ruleIndex, -1)}
                    >
                      <ArrowUp data-icon="inline-start" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      aria-label={titleForLocale(
                        locale,
                        "下移规则",
                        "Move rule down",
                      )}
                      disabled={
                        ruleIndex ===
                        upstreamParamOverrideConfig.rules.length - 1
                      }
                      onClick={() => onMoveParamOverrideRule(ruleIndex, 1)}
                    >
                      <ArrowDown data-icon="inline-start" />
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="text-muted-foreground"
                      aria-label={titleForLocale(
                        locale,
                        "删除规则",
                        "Remove rule",
                      )}
                      onClick={() => onRemoveParamOverrideRule(ruleIndex)}
                    >
                      <Trash2 data-icon="inline-start" />
                    </Button>
                  </div>
                </div>
                {rule.matchType === "exact" ? (
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "模型名称", "Models")}
                    </FieldLabel>
                    <Textarea
                      className="min-h-[84px]"
                      value={rule.models}
                      onChange={(event) =>
                        onUpdateParamOverrideRule(ruleIndex, {
                          models: event.target.value,
                        })
                      }
                      placeholder={"claude-3-opus\nclaude-3-sonnet"}
                    />
                  </Field>
                ) : (
                  <Field>
                    <FieldLabel>
                      {titleForLocale(locale, "模型正则", "Model regex")}
                    </FieldLabel>
                    <Input
                      value={rule.pattern}
                      onChange={(event) =>
                        onUpdateParamOverrideRule(ruleIndex, {
                          pattern: event.target.value,
                        })
                      }
                      placeholder="^claude-"
                    />
                  </Field>
                )}
                <Field>
                  <FieldLabel>
                    {titleForLocale(locale, "覆盖参数", "Override params")}
                  </FieldLabel>
                  <Textarea
                    className="min-h-[84px] font-mono text-sm"
                    value={rule.override}
                    onChange={(event) =>
                      onUpdateParamOverrideRule(ruleIndex, {
                        override: event.target.value,
                      })
                    }
                    placeholder={'{ "max_tokens": 8192 }'}
                  />
                  <FieldDescription>
                    {titleForLocale(
                      locale,
                      "JSON 对象，深合并进匹配模型的上游请求体；不可覆盖 model。",
                      "JSON object, deep-merged into matched models' upstream body; cannot override model.",
                    )}
                  </FieldDescription>
                </Field>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">
            {titleForLocale(locale, "暂无规则", "No rules")}
          </div>
        )}
        <FieldDescription>
          {titleForLocale(
            locale,
            "合并优先级：请求体 < 全局 < 规则 < 渠道覆盖（后者覆盖前者）。",
            "Merge priority: body < global < rules < channel override (later wins).",
          )}
        </FieldDescription>
      </div>
    </FieldGroup>
  );
}
