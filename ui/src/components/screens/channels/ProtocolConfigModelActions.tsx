import { Plus, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { ProtocolMultiSelect } from "@/components/ui/ProtocolMultiSelect";
import { Separator } from "@/components/ui/Separator";
import { Switch } from "@/components/ui/Switch";
import type { FormProtocolConfig, Locale } from "./channelShared";
import {
  classifyModelQueryInput,
  isValidModelQueryRegex,
} from "./channelShared";

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
  const modelQueryInput = protocolConfig.manual_model_name.trim();
  const modelQueryKind = classifyModelQueryInput(modelQueryInput);
  const isRegexQuery = modelQueryKind === "regex";
  const isValidRegexQuery =
    !isRegexQuery || isValidModelQueryRegex(modelQueryInput);
  const isAddModelDisabled =
    !hasActiveCredentials ||
    modelQueryKind !== "plain" ||
    !protocolConfig.manual_protocols.length;
  const isFetchModelsDisabled =
    fetchingProtocolConfigIndex === protocolConfigIndex ||
    !hasActiveBaseUrl ||
    !hasActiveCredentials ||
    !protocolConfig.manual_protocols.length ||
    modelQueryKind === "plain" ||
    !isValidRegexQuery;

  return (
    <div className="grid gap-3 pt-1">
      <Separator />
      <FieldGroup className="gap-3">
        <div className="grid min-w-0 gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(180px,0.42fr)_auto_auto] lg:items-end">
          <Field data-invalid={isRegexQuery && !isValidRegexQuery}>
            <FieldLabel>
              {locale === "zh-CN" ? "模型名称" : "Model name"}
            </FieldLabel>
            <Input
              className="w-full min-w-0"
              value={protocolConfig.manual_model_name}
              aria-invalid={isRegexQuery && !isValidRegexQuery}
              onChange={(event) => {
                const nextValue = event.target.value;
                const nextKind = classifyModelQueryInput(nextValue);
                onUpdate({
                  manual_model_name: nextValue,
                  match_regex: nextKind === "plain" ? "" : nextValue,
                  auto_sync_enabled:
                    nextKind === "regex"
                      ? protocolConfig.auto_sync_enabled
                      : false,
                });
              }}
              onKeyDown={(event) => {
                if (event.key !== "Enter" || isAddModelDisabled) return;
                event.preventDefault();
                onAddManualModel();
              }}
              placeholder={
                locale === "zh-CN"
                  ? "模型名、正则，或留空"
                  : "Model name, regex, or empty"
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
          <Button
            type="button"
            onClick={onFetchModels}
            disabled={isFetchModelsDisabled}
          >
            <RefreshCcw
              data-icon="inline-start"
              className={
                fetchingProtocolConfigIndex === protocolConfigIndex
                  ? "animate-spin"
                  : ""
              }
            />
            {locale === "zh-CN" ? "获取更多" : "Fetch more"}
          </Button>
        </div>
        {isRegexQuery ? (
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm text-foreground">
              {locale === "zh-CN" ? "自动同步" : "Auto sync"}
            </div>
            <Switch
              checked={protocolConfig.auto_sync_enabled}
              onCheckedChange={(checked) =>
                onUpdate({
                  auto_sync_enabled: checked,
                  match_regex: protocolConfig.manual_model_name,
                })
              }
              disabled={!isValidRegexQuery}
            />
          </div>
        ) : null}
      </FieldGroup>
    </div>
  );
}
