import { CircleHelp, Plus, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { ProtocolMultiSelect } from "@/components/ui/ProtocolMultiSelect";
import { Separator } from "@/components/ui/Separator";
import { Switch } from "@/components/ui/Switch";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
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
  const isAddModelDisabled =
    !hasActiveCredentials ||
    !manualModelName ||
    !protocolConfig.manual_protocols.length;
  const isFetchModelsDisabled =
    fetchingProtocolConfigIndex !== null ||
    !hasActiveBaseUrl ||
    !hasActiveCredentials ||
    !protocolConfig.manual_protocols.length;
  const isFetchPending = fetchingProtocolConfigIndex === protocolConfigIndex;

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
        <div className="grid min-w-0 gap-2 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-end">
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "上游筛选" : "Upstream filter"}
            </FieldLabel>
            <Input
              value={protocolConfig.model_filter}
              onChange={(event) =>
                onUpdate({ model_filter: event.target.value })
              }
              placeholder={
                locale === "zh-CN"
                  ? "筛选上游模型（支持正则），留空则匹配全部。"
                  : "Filter upstream models (supports regular expressions); leave blank to match all."
              }
            />
          </Field>
          <Button
            type="button"
            variant="outline"
            onClick={onFetchModels}
            disabled={isFetchModelsDisabled}
          >
            <RefreshCcw
              data-icon="inline-start"
              className={isFetchPending ? "animate-spin" : undefined}
            />
            {locale === "zh-CN" ? "从上游选择" : "Select from upstream"}
          </Button>
          <div className="flex items-center gap-1">
            <label className="flex h-9 cursor-pointer items-center gap-2 px-2 text-sm font-medium">
              <Switch
                checked={protocolConfig.sync_new_models}
                onCheckedChange={(checked) =>
                  onUpdate({ sync_new_models: checked })
                }
              />
              <span>{locale === "zh-CN" ? "同步" : "Sync"}</span>
            </label>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={locale === "zh-CN" ? "同步说明" : "Sync details"}
                >
                  <CircleHelp />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top" align="end" className="max-w-sm">
                {locale === "zh-CN"
                  ? "开启后，新添加或从上游选择的模型默认为同步；关闭时默认为手动。此开关不会修改模型总览中的现有模型。上游筛选仅用于本次获取，不会保存。"
                  : "When enabled, newly added or selected upstream models default to synced; otherwise they default to manual. This switch does not change existing models in the overview. The upstream filter is used only for this fetch and is not saved."}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      </FieldGroup>
    </div>
  );
}
