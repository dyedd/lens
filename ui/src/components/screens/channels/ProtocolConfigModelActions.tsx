import { Plus, RefreshCcw, TriangleAlert } from "lucide-react";
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
              value={protocolConfig.match_regex}
              onChange={(event) =>
                onUpdate({ match_regex: event.target.value })
              }
              placeholder={
                locale === "zh-CN"
                  ? "正则，可留空表示全部。多条用 | 分隔，如 gpt-|claude-"
                  : "Regex, empty means all. Use | for multiple, e.g. gpt-|claude-"
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
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                onClick={onSyncAllModels}
                disabled={isFetchModelsDisabled}
              >
                {isModelActionPending ? (
                  <RefreshCcw
                    data-icon="inline-start"
                    className="animate-spin"
                  />
                ) : (
                  <TriangleAlert data-icon="inline-start" />
                )}
                {locale === "zh-CN" ? "全部同步" : "Sync all"}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top" align="end" className="max-w-sm">
              {locale === "zh-CN"
                ? "覆盖操作：按上游筛选拉取全部模型并标记为「同步」，上游已没有的同步模型会被移除，手动模型保持不动。保存后，模型组会跟着移除指向已删除模型的条目。"
                : "Overwrites: pulls every upstream model matching the filter and marks it synced, drops synced models the upstream no longer returns, and leaves manual models alone. On save, model groups drop entries pointing to deleted models."}
            </TooltipContent>
          </Tooltip>
        </div>
        <p className="text-xs text-muted-foreground">
          {locale === "zh-CN"
            ? "「从上游选择」勾选的模型标记为手动，由你维护；「全部同步」让同步模型与上游保持一致，之后后台会自动增删。"
            : "Models picked via Select from upstream are marked manual and stay under your control; Sync all makes the synced set match the upstream, and the background job keeps it in step."}
        </p>
      </FieldGroup>
    </div>
  );
}
