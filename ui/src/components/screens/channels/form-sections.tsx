"use client";

import {
  ChevronDown,
  Ellipsis,
  Plus,
  RefreshCcw,
  Trash2,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AppDialogContent, Dialog } from "@/components/ui/dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Combobox, ComboboxOption } from "@/components/ui/combobox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  activeBaseUrlValue,
  baseUrlLabel,
  compactProtocolLabel,
  credentialLabel,
  defaultProtocolConfigName,
  formBaseUrlsForPayload,
  FormProtocolConfig,
  FormState,
  HeaderItem,
  Locale,
  modelSupportedProtocols,
  protocolBadgeClassName,
  protocolConfigCredentialKeys,
  protocolLabel,
  resolveBaseUrlId,
} from "./shared";

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
}: {
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
  onAddManualModel: (index: number, credentialIds: string[]) => void;
  onFetchModels: (index: number) => void;
  onOpenAdvanced: (index: number) => void;
}) {
  const submittedBaseUrls = formBaseUrlsForPayload(form);
  const submittedBaseUrlIds = new Set(submittedBaseUrls.map((item) => item.id));
  const protocolConfigDuplicated = protocolConfigCredentialKeys(
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
  const selectedCredentialId = protocolConfig.credential_id;
  const selectedCredentialActive = activeCredentialIds.has(selectedCredentialId);
  const selectedCredentialKnown = credentialOptions.some(
    (item) => item.id === selectedCredentialId,
  );
  const activeCredentialCount = activeCredentialIds.size;
  const credentialLabelById = new Map(
    credentialOptions.map((item) => [item.id, item.display_name]),
  );
  const visibleModels = protocolConfig.models.map((model, modelIndex) => ({
    model,
    modelIndex,
  }));

  return (
    <div className="grid gap-3 rounded-lg border border-border bg-muted/30 p-4 shadow-sm">
      <div className="flex flex-col gap-3">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,0.95fr)_minmax(0,0.95fr)_32px_auto] xl:items-end">
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "组合名称" : "Combination name"}
            </FieldLabel>
            <Input
              className="w-full min-w-0"
              value={protocolConfig.name}
              onChange={(event) =>
                onUpdateProtocolConfig(protocolConfigIndex, {
                  name: event.target.value,
                })
              }
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
              onChange={(event) =>
                onUpdateProtocolConfig(protocolConfigIndex, {
                  base_url_id: event.target.value,
                })
              }
            >
              {form.base_urls.map((item, baseUrlIndex) => (
                <ComboboxOption key={item.id} value={item.id}>
                  {baseUrlLabel(item, baseUrlIndex, locale)}
                </ComboboxOption>
              ))}
            </Combobox>
          </Field>
          <Field>
            <FieldLabel>
              {locale === "zh-CN" ? "默认密钥" : "Default key"}
            </FieldLabel>
            <Combobox
              className="w-full"
              value={selectedCredentialId}
              onChange={(event) => {
                onUpdateProtocolConfig(protocolConfigIndex, {
                  credential_id: event.target.value,
                });
              }}
            >
              {selectedCredentialId && !selectedCredentialKnown ? (
                <ComboboxOption value={selectedCredentialId} disabled>
                  {locale === "zh-CN"
                    ? `无效密钥：${selectedCredentialId}`
                    : `Invalid key: ${selectedCredentialId}`}
                </ComboboxOption>
              ) : null}
              {credentialOptions.length ? (
                credentialOptions.map((item) => (
                  <ComboboxOption key={item.id} value={item.id}>
                    {item.display_name}
                  </ComboboxOption>
                ))
              ) : (
                <ComboboxOption value="" disabled>
                  {locale === "zh-CN" ? "暂无可用密钥" : "No available key"}
                </ComboboxOption>
              )}
            </Combobox>
          </Field>
          <div className="flex h-8 w-8 items-center justify-center xl:self-end">
            <Switch
              checked={protocolConfig.enabled}
              onCheckedChange={(checked) =>
                onUpdateProtocolConfig(protocolConfigIndex, {
                  enabled: checked,
                })
              }
            />
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2 xl:col-start-5 xl:row-start-1 xl:self-end">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="text-muted-foreground"
              onClick={() => onOpenAdvanced(protocolConfigIndex)}
            >
              <Ellipsis size={16} />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="text-destructive hover:text-destructive"
              onClick={() => onRemoveProtocolConfig(protocolConfigIndex)}
            >
              <X size={16} />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="default"
              className="text-muted-foreground hover:text-foreground"
              onClick={() =>
                onUpdateProtocolConfig(protocolConfigIndex, {
                  expanded: !protocolConfig.expanded,
                })
              }
            >
              <span>{locale === "zh-CN" ? "模型列表" : "Models"}</span>
              <ChevronDown
                size={16}
                className={cn(
                  "transition-transform",
                  protocolConfig.expanded ? "rotate-180" : "",
                )}
              />
            </Button>
          </div>
        </div>

        {protocolConfigDuplicated ? (
          <div className="text-sm text-destructive">
            {locale === "zh-CN"
              ? "地址来源和协议重复"
              : "Duplicate Base URL and protocols"}
          </div>
        ) : null}

        {protocolConfig.expanded ? (
          <div className="grid gap-3 pt-1">
            <Separator />
            <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <FieldGroup className="gap-2">
                <div className="text-sm font-medium text-foreground">
                  {locale === "zh-CN" ? "手动添加模型" : "Add model manually"}
                </div>
                <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "模型名称" : "Model name"}
                    </FieldLabel>
                    <Input
                      className="w-full min-w-0"
                      value={protocolConfig.manual_model_name}
                      onChange={(event) =>
                        onUpdateProtocolConfig(protocolConfigIndex, {
                          manual_model_name: event.target.value,
                        })
                      }
                      onKeyDown={(event) => {
                        if (event.key !== "Enter") return;
                        event.preventDefault();
                        onAddManualModel(protocolConfigIndex, [
                          selectedCredentialId,
                        ]);
                      }}
                      placeholder={
                        locale === "zh-CN" ? "完整模型名" : "Exact model name"
                      }
                    />
                  </Field>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() =>
                      onAddManualModel(protocolConfigIndex, [
                        selectedCredentialId,
                      ])
                    }
                    disabled={
                      !selectedCredentialActive ||
                      !protocolConfig.manual_model_name.trim()
                    }
                  >
                    <Plus data-icon="inline-start" />
                    {locale === "zh-CN" ? "添加模型" : "Add model"}
                  </Button>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  className="justify-self-start text-muted-foreground hover:text-foreground"
                  onClick={() =>
                    onAddManualModel(
                      protocolConfigIndex,
                      Array.from(activeCredentialIds),
                    )
                  }
                  disabled={
                    activeCredentialCount === 0 ||
                    !protocolConfig.manual_model_name.trim()
                  }
                >
                  <Plus data-icon="inline-start" />
                  {locale === "zh-CN" ? "添加到全部密钥" : "Add to all keys"}
                </Button>
              </FieldGroup>
              <FieldGroup className="gap-2">
                <div className="text-sm font-medium text-foreground">
                  {locale === "zh-CN"
                    ? "从上游获取模型"
                    : "Fetch upstream models"}
                </div>
                <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "模型过滤" : "Model filter"}
                    </FieldLabel>
                    <Input
                      className="w-full min-w-0"
                      value={protocolConfig.match_regex}
                      onChange={(event) =>
                        onUpdateProtocolConfig(protocolConfigIndex, {
                          match_regex: event.target.value,
                        })
                      }
                      placeholder={
                        locale === "zh-CN"
                          ? "正则表达式，留空获取全部"
                          : "Regex, empty fetches all"
                      }
                    />
                  </Field>
                  <Button
                    type="button"
                    onClick={() => onFetchModels(protocolConfigIndex)}
                    disabled={
                      fetchingProtocolConfigIndex === protocolConfigIndex ||
                      !activeBaseUrlValue(form, protocolConfig).trim() ||
                      activeCredentialCount === 0
                    }
                  >
                    <RefreshCcw
                      data-icon="inline-start"
                      className={
                        fetchingProtocolConfigIndex === protocolConfigIndex
                          ? "animate-spin"
                          : ""
                      }
                    />
                    {locale === "zh-CN" ? "获取模型" : "Fetch models"}
                  </Button>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm text-foreground">
                    {locale === "zh-CN" ? "自动同步" : "Auto sync"}
                  </div>
                  <Switch
                    checked={protocolConfig.auto_sync_enabled}
                    onCheckedChange={(checked) =>
                      onUpdateProtocolConfig(protocolConfigIndex, {
                        auto_sync_enabled: checked,
                      })
                    }
                  />
                </div>
              </FieldGroup>
            </div>

            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-medium text-foreground">
                {locale === "zh-CN" ? "已选模型" : "Selected models"}
              </div>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() =>
                  onUpdateProtocolConfig(protocolConfigIndex, { models: [] })
                }
                disabled={!visibleModels.length}
              >
                <Trash2 data-icon="inline-start" />
                {locale === "zh-CN" ? "清空全部" : "Clear all"}
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              {visibleModels.length ? (
                <div className="flex w-full flex-col gap-1.5">
                  {visibleModels.map(({ model, modelIndex }) => (
                    <div
                      key={
                        model.id ||
                        `${model.credential_id}-${model.model_name}-${modelIndex}`
                      }
                      className={cn(
                        "flex min-w-0 items-center gap-2 rounded-md border px-2.5 py-1.5",
                        model.enabled
                          ? "border-border bg-background"
                          : "border-muted bg-muted/30 opacity-65",
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm text-foreground">
                          {model.model_name}
                        </div>
                        <div className="truncate text-xs text-muted-foreground">
                          {credentialLabelById.get(model.credential_id) ||
                            (locale === "zh-CN" ? "未知密钥" : "Unknown key")}
                        </div>
                      </div>
                      {modelSupportedProtocols(model).map((item) => (
                        <Badge
                          key={item}
                          variant="outline"
                          title={
                            locale === "zh-CN"
                              ? `客户端协议：${protocolLabel(item, locale)}`
                              : `Client protocol: ${protocolLabel(item, locale)}`
                          }
                          className={cn(
                            "max-w-[140px] truncate",
                            protocolBadgeClassName(item),
                          )}
                        >
                          {compactProtocolLabel(item)}
                        </Badge>
                      ))}
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-destructive"
                        onClick={() =>
                          onUpdateProtocolConfig(protocolConfigIndex, {
                            models: protocolConfig.models.filter(
                              (_, currentIndex) => currentIndex !== modelIndex,
                            ),
                          })
                        }
                      >
                        <X size={14} />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  {locale === "zh-CN" ? "当前没有模型" : "No models selected"}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function AdvancedProtocolConfigDialog({
  open,
  protocolConfig,
  protocolConfigIndex,
  locale,
  onOpenChange,
  onUpdateProtocolConfig,
  onUpdateProtocolConfigHeader,
}: {
  open: boolean;
  protocolConfig: FormProtocolConfig | undefined;
  protocolConfigIndex: number | null;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onUpdateProtocolConfig: (
    index: number,
    patch: Partial<FormProtocolConfig>,
  ) => void;
  onUpdateProtocolConfigHeader: (
    protocolConfigIndex: number,
    headerIndex: number,
    patch: Partial<HeaderItem>,
  ) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {protocolConfigIndex !== null && protocolConfig ? (
        <AppDialogContent
          className="max-w-3xl"
          title={locale === "zh-CN" ? "更多设置" : "More settings"}
        >
          <div className="grid gap-4">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="protocol-proxy-mode">
                  {locale === "zh-CN" ? "代理模式" : "Proxy mode"}
                </FieldLabel>
                <Select
                  value={protocolConfig.proxy_mode}
                  onValueChange={(value) =>
                    onUpdateProtocolConfig(protocolConfigIndex, {
                      proxy_mode: value as FormProtocolConfig["proxy_mode"],
                    })
                  }
                >
                  <SelectTrigger id="protocol-proxy-mode" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inherit">
                      {locale === "zh-CN" ? "跟随系统代理" : "Use system proxy"}
                    </SelectItem>
                    <SelectItem value="direct">
                      {locale === "zh-CN" ? "不使用代理" : "Direct"}
                    </SelectItem>
                    <SelectItem value="custom">
                      {locale === "zh-CN" ? "自定义代理" : "Custom proxy"}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              {protocolConfig.proxy_mode === "custom" ? (
                <Field>
                  <FieldLabel htmlFor="protocol-proxy">
                    {locale === "zh-CN" ? "代理地址" : "Proxy URL"}
                  </FieldLabel>
                  <Input
                    id="protocol-proxy"
                    value={protocolConfig.channel_proxy}
                    onChange={(event) =>
                      onUpdateProtocolConfig(protocolConfigIndex, {
                        channel_proxy: event.target.value,
                      })
                    }
                    placeholder="http://127.0.0.1:7890"
                  />
                </Field>
              ) : null}
            </FieldGroup>
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-foreground">
                  {locale === "zh-CN" ? "请求头" : "Headers"}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    onUpdateProtocolConfig(protocolConfigIndex, {
                      headers: [
                        ...protocolConfig.headers,
                        { key: "", value: "" },
                      ],
                    })
                  }
                >
                  <Plus data-icon="inline-start" />
                  {locale === "zh-CN" ? "添加" : "Add"}
                </Button>
              </div>
              {protocolConfig.headers.map((header, headerIndex) => (
                <div
                  key={headerIndex}
                  className="grid gap-3 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
                >
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "请求头名称" : "Header key"}
                    </FieldLabel>
                    <Input
                      value={header.key}
                      onChange={(event) =>
                        onUpdateProtocolConfigHeader(
                          protocolConfigIndex,
                          headerIndex,
                          {
                            key: event.target.value,
                          },
                        )
                      }
                      placeholder={
                        locale === "zh-CN" ? "请求头名称" : "Header-Key"
                      }
                    />
                  </Field>
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "请求头值" : "Header value"}
                    </FieldLabel>
                    <Input
                      value={header.value}
                      onChange={(event) =>
                        onUpdateProtocolConfigHeader(
                          protocolConfigIndex,
                          headerIndex,
                          {
                            value: event.target.value,
                          },
                        )
                      }
                      placeholder={
                        locale === "zh-CN" ? "请求头值" : "Header-Value"
                      }
                    />
                  </Field>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="text-muted-foreground"
                    onClick={() =>
                      onUpdateProtocolConfig(protocolConfigIndex, {
                        headers:
                          protocolConfig.headers.length > 1
                            ? protocolConfig.headers.filter(
                              (_, currentIndex) =>
                                currentIndex !== headerIndex,
                            )
                            : protocolConfig.headers,
                      })
                    }
                  >
                    <X size={16} />
                  </Button>
                </div>
              ))}
            </div>
            <Field>
              <FieldLabel htmlFor="protocol-param-override">
                {locale === "zh-CN" ? "参数覆盖" : "Param Override"}
              </FieldLabel>
              <Textarea
                id="protocol-param-override"
                className="min-h-24"
                value={protocolConfig.param_override}
                onChange={(event) =>
                  onUpdateProtocolConfig(protocolConfigIndex, {
                    param_override: event.target.value,
                  })
                }
              />
              <FieldDescription>
                {locale === "zh-CN"
                  ? "填写 JSON 片段用于覆盖请求参数。"
                  : "Use a JSON snippet to override request params."}
              </FieldDescription>
            </Field>
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}
