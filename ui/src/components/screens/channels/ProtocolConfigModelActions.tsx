import { Plus, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { ProtocolMultiSelect } from "@/components/ui/ProtocolMultiSelect";
import { Separator } from "@/components/ui/Separator";
import { Switch } from "@/components/ui/Switch";
import type { FormProtocolConfig, Locale } from "./channelShared";

type Props = {
  protocolConfig: FormProtocolConfig;
  protocolConfigIndex: number;
  locale: Locale;
  fetchingProtocolConfigIndex: number | null;
  hasActiveBaseUrl: boolean;
  hasActiveCredentials: boolean;
  onUpdate: (patch: Partial<FormProtocolConfig>) => void;
  onAddManualModel: () => void;
  onFetchModels: () => void;
};

/** Renders manual model entry and model discovery actions for a protocol config. */
export function ProtocolConfigModelActions({
  protocolConfig,
  protocolConfigIndex,
  locale,
  fetchingProtocolConfigIndex,
  hasActiveBaseUrl,
  hasActiveCredentials,
  onUpdate,
  onAddManualModel,
  onFetchModels,
}: Props) {
  const manualModelName = protocolConfig.manual_model_name.trim();
  const matchRegex = protocolConfig.match_regex.trim();
  const isMatchRegexInvalid = protocolConfig.auto_sync_enabled && !matchRegex;
  const isAddModelDisabled =
    !hasActiveCredentials ||
    !manualModelName ||
    !protocolConfig.manual_protocols.length;
  const isFetchModelsDisabled =
    fetchingProtocolConfigIndex !== null ||
    !hasActiveBaseUrl ||
    !hasActiveCredentials ||
    !protocolConfig.manual_protocols.length;
  const isModelActionPending =
    fetchingProtocolConfigIndex === protocolConfigIndex;

  return (
    <div className="grid gap-3 pt-1">
      <Separator />
      <FieldGroup className="gap-3">
        <div className="grid min-w-0 gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(180px,0.42fr)_auto] lg:items-end">
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "模型名称" : "Model name"}
            </FieldLabel>
            <Input
              className="w-full min-w-0"
              value={protocolConfig.manual_model_name}
              onChange={(event) =>
                onUpdate({ manual_model_name: event.target.value })
              }
              onKeyDown={(event) => {
                if (event.key !== "Enter" || isAddModelDisabled) return;
                event.preventDefault();
                onAddManualModel();
              }}
              placeholder={
                locale === "zh-CN" ? "输入模型名称" : "Enter a model name"
              }
            />
          </Field>
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "客户端协议" : "Client protocols"}
            </FieldLabel>
            <ProtocolMultiSelect
              value={protocolConfig.manual_protocols}
              onChange={(next) => onUpdate({ manual_protocols: next })}
              locale={locale}
              invalid={protocolConfig.manual_protocols.length === 0}
            />
          </Field>
          <Button
            type="button"
            variant="outline"
            onClick={onAddManualModel}
            disabled={isAddModelDisabled}
          >
            <Plus data-icon="inline-start" />
            {locale === "zh-CN" ? "添加模型" : "Add model"}
          </Button>
        </div>
        <div className="grid min-w-0 gap-2 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <Field data-invalid={isMatchRegexInvalid}>
            <FieldLabel>
              {locale === "zh-CN" ? "上游筛选" : "Upstream filter"}
            </FieldLabel>
            <Input
              value={protocolConfig.match_regex}
              aria-invalid={isMatchRegexInvalid}
              onChange={(event) =>
                onUpdate({ match_regex: event.target.value })
              }
              placeholder={
                locale === "zh-CN"
                  ? "正则表达式，可留空"
                  : "Regular expression, optional"
              }
            />
          </Field>
          <Button
            type="button"
            onClick={onFetchModels}
            disabled={isFetchModelsDisabled}
          >
            <RefreshCcw
              data-icon="inline-start"
              className={isModelActionPending ? "animate-spin" : undefined}
            />
            {locale === "zh-CN" ? "从上游选择" : "Select from upstream"}
          </Button>
        </div>
        <Separator />
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-medium text-foreground">
            {locale === "zh-CN" ? "自动同步" : "Auto sync"}
          </div>
          <Switch
            checked={protocolConfig.auto_sync_enabled}
            onCheckedChange={(checked) =>
              onUpdate({ auto_sync_enabled: checked })
            }
          />
        </div>
      </FieldGroup>
    </div>
  );
}
