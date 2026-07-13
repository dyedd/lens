import { Plus } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Separator } from "@/components/ui/Separator";
import { titleForLocale } from "@/lib/I18nContext";

import type { UpstreamHeaderSettingsProps } from "./gatewaySettingsTypes";
import { HeaderRows } from "./HeaderRows";
import { UpstreamHeaderRuleCard } from "./UpstreamHeaderRuleCard";

/** Renders global and model-specific upstream request-header settings. */
export function UpstreamHeaderSettings({
  locale,
  config,
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
}: UpstreamHeaderSettingsProps) {
  return (
    <div className="flex flex-col gap-5 rounded-lg border bg-muted/20 p-4">
      <HeaderRows
        title={titleForLocale(locale, "全局请求头", "Global headers")}
        headers={config.global}
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
      {config.rules.length ? (
        <div className="flex flex-col gap-4">
          {config.rules.map((rule, ruleIndex) => (
            <UpstreamHeaderRuleCard
              key={rule.id}
              locale={locale}
              rule={rule}
              ruleIndex={ruleIndex}
              ruleCount={config.rules.length}
              onUpdate={(patch) => onUpdateRule(ruleIndex, patch)}
              onRemove={() => onRemoveRule(ruleIndex)}
              onMove={(direction) => onMoveRule(ruleIndex, direction)}
              onAddHeader={() => onAddRuleHeader(ruleIndex)}
              onUpdateHeader={(headerIndex, patch) =>
                onUpdateRuleHeader(ruleIndex, headerIndex, patch)
              }
              onRemoveHeader={(headerIndex) =>
                onRemoveRuleHeader(ruleIndex, headerIndex)
              }
            />
          ))}
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">
          {titleForLocale(locale, "暂无规则", "No rules")}
        </div>
      )}
    </div>
  );
}
