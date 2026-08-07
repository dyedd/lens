import { CircleHelp, Plus, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { ProtocolMultiSelect } from "@/components/ui/ProtocolMultiSelect";
import { Separator } from "@/components/ui/Separator";
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
  onSyncAllModels: () => void;
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
  onSyncAllModels,
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
                  ? "筛选上游模型（支持正则）；留空表示全部；如 gpt-|claude-"
                  : "Filter upstream models (regex supported). Empty means all; e.g. gpt-|claude-"
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
              className={isModelActionPending ? "animate-spin" : undefined}
            />
            {locale === "zh-CN" ? "从上游选择" : "Select from upstream"}
          </Button>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              onClick={onSyncAllModels}
              disabled={isFetchModelsDisabled}
            >
              <RefreshCcw
                data-icon="inline-start"
                className={isModelActionPending ? "animate-spin" : undefined}
              />
              {locale === "zh-CN" ? "全部同步" : "Sync all"}
            </Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={
                    locale === "zh-CN" ? "全部同步说明" : "Sync all details"
                  }
                >
                  <CircleHelp />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top" align="end" className="max-w-sm">
                {locale === "zh-CN" ? (
                  <div className="grid gap-2">
                    <p>
                      覆盖操作：按本次上游筛选拉取全部模型并标记为“同步”。上游已没有的同步模型会被移除，手动模型保持不动；保存后，后台只会继续协调这批同步模型。筛选条件仅用于本次操作，不会保存。
                      已删除模型对应的模型组条目也会随之移除。
                    </p>
                  </div>
                ) : (
                  <div className="grid gap-2">
                    <p>
                      Replace this combination&apos;s synced models with the
                      models returned by this one-time upstream filter. Missing
                      synced models are removed, while manual models stay
                      unchanged. After saving, background sync reconciles only
                      these exact models; the filter itself is not saved.
                      Removed models are also removed from related model groups.
                    </p>
                  </div>
                )}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      </FieldGroup>
    </div>
  );
}
