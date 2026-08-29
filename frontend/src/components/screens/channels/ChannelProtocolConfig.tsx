import { ChevronDown, Settings, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import { Field, FieldLabel } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { cn } from "@/lib/classNames";
import { CredentialMultiSelect } from "./CredentialMultiSelect";
import { formBaseUrlsForPayload } from "./channelFormConversion";
import {
  activeBaseUrlValue,
  protocolConfigSelectedCredentialIds,
  resolveBaseUrlId,
} from "./channelFormUtils";
import { protocolConfigCredentialKeys } from "./channelFormValidationUtils";
import {
  baseUrlLabel,
  credentialLabel,
  defaultProtocolConfigName,
} from "./channelLabels";
import type { FormProtocolConfig, FormState, Locale } from "./channelTypes";
import { ProtocolConfigModelActions } from "./ProtocolConfigModelActions";

type Props = {
  form: FormState;
  protocolConfig: FormProtocolConfig;
  protocolConfigIndex: number;
  locale: Locale;
  fetchingProtocolConfigIndex: number | null;
  duplicatedProtocolConfigKeys: Set<string>;
  onUpdateProtocolConfig: (
    index: number,
    patch: Partial<FormProtocolConfig>,
  ) => void;
  onRemoveProtocolConfig: (index: number) => void;
  onAddManualModel: (index: number) => void;
  onFetchModels: (index: number) => void;
  onOpenAdvanced: (index: number) => void;
};

/** Renders and updates one channel protocol configuration. */
export function ProtocolConfigItem({
  form,
  protocolConfig,
  protocolConfigIndex,
  locale,
  fetchingProtocolConfigIndex,
  duplicatedProtocolConfigKeys,
  onUpdateProtocolConfig,
  onRemoveProtocolConfig,
  onAddManualModel,
  onFetchModels,
  onOpenAdvanced,
}: Props) {
  const submittedBaseUrlIds = new Set(
    formBaseUrlsForPayload(form).map((item) => item.id),
  );
  const isDuplicated = protocolConfigCredentialKeys(
    protocolConfig,
    submittedBaseUrlIds,
  ).some((key) => duplicatedProtocolConfigKeys.has(key));
  const activeCredentialIds = new Set(
    form.credentials
      .filter((item) => item.enabled && item.api_key.trim())
      .map((item) => item.id),
  );
  const credentialOptions = form.credentials.map((item, index) => ({
    ...item,
    display_name: credentialLabel(item, index, locale),
  }));
  const selectedCredentialIds =
    protocolConfigSelectedCredentialIds(protocolConfig);
  const hasActiveCredentials = selectedCredentialIds.some((id) =>
    activeCredentialIds.has(id),
  );
  const update = (patch: Partial<FormProtocolConfig>) =>
    onUpdateProtocolConfig(protocolConfigIndex, patch);

  return (
    <div
      className="grid min-w-0 gap-3 border-b pb-3 last:border-b-0 last:pb-0"
      data-protocol-config-index={protocolConfigIndex}
      tabIndex={-1}
    >
      <div className="flex flex-col gap-3">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,0.95fr)_minmax(0,0.95fr)_32px_auto] xl:items-end">
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "协议配置名称" : "Protocol config name"}
            </FieldLabel>
            <Input
              className="w-full min-w-0"
              value={protocolConfig.name}
              onChange={(event) => update({ name: event.target.value })}
              placeholder={defaultProtocolConfigName(
                protocolConfigIndex,
                locale,
              )}
            />
          </Field>
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "地址来源" : "Base URL"}
            </FieldLabel>
            <Combobox
              className="w-full"
              value={resolveBaseUrlId(
                form.base_urls,
                protocolConfig.base_url_id,
              )}
              onChange={(event) => update({ base_url_id: event.target.value })}
            >
              {form.base_urls.map((item, baseUrlIndex) => (
                <ComboboxOption key={item.id} value={item.id}>
                  {baseUrlLabel(item, baseUrlIndex, locale)}
                </ComboboxOption>
              ))}
            </Combobox>
          </Field>
          <Field>
            <FieldLabel>{locale === "zh-CN" ? "密钥" : "Key"}</FieldLabel>
            <CredentialMultiSelect
              value={selectedCredentialIds}
              options={credentialOptions}
              locale={locale}
              invalid={!hasActiveCredentials}
              onChange={(next) => update({ credential_ids: next })}
            />
          </Field>
          <div className="flex size-8 items-center justify-center xl:self-end">
            <Switch
              checked={protocolConfig.enabled}
              onCheckedChange={(checked) => update({ enabled: checked })}
            />
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2 xl:col-start-5 xl:row-start-1 xl:self-end">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="text-muted-foreground"
              aria-label={
                locale === "zh-CN" ? "协议配置设置" : "Protocol config settings"
              }
              title={
                locale === "zh-CN" ? "协议配置设置" : "Protocol config settings"
              }
              onClick={() => onOpenAdvanced(protocolConfigIndex)}
            >
              <Settings />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="text-destructive hover:text-destructive"
              aria-label={
                locale === "zh-CN" ? "删除协议配置" : "Delete protocol config"
              }
              title={
                locale === "zh-CN" ? "删除协议配置" : "Delete protocol config"
              }
              onClick={() => onRemoveProtocolConfig(protocolConfigIndex)}
            >
              <Trash2 />
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => update({ expanded: !protocolConfig.expanded })}
            >
              <span>{locale === "zh-CN" ? "模型操作" : "Model actions"}</span>
              <ChevronDown
                className={cn(
                  "transition-transform",
                  protocolConfig.expanded && "rotate-180",
                )}
              />
            </Button>
          </div>
        </div>
        {isDuplicated ? (
          <div className="text-sm text-destructive">
            {locale === "zh-CN"
              ? "地址来源、密钥和协议重复"
              : "Duplicate Base URL, key, and protocols"}
          </div>
        ) : null}
        {protocolConfig.expanded ? (
          <ProtocolConfigModelActions
            protocolConfig={protocolConfig}
            protocolConfigIndex={protocolConfigIndex}
            locale={locale}
            fetchingProtocolConfigIndex={fetchingProtocolConfigIndex}
            hasActiveBaseUrl={Boolean(
              activeBaseUrlValue(form, protocolConfig).trim(),
            )}
            hasActiveCredentials={hasActiveCredentials}
            onUpdate={update}
            onAddManualModel={() => onAddManualModel(protocolConfigIndex)}
            onFetchModels={() => onFetchModels(protocolConfigIndex)}
          />
        ) : null}
      </div>
    </div>
  );
}
