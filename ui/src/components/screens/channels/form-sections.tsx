"use client";

import { useState } from "react";
import {
  ChevronDown,
  Plus,
  RefreshCcw,
  Search,
  Settings,
  Trash2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { AppDialogContent, Dialog } from "@/components/ui/dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Combobox, ComboboxOption } from "@/components/ui/combobox";
import { ProtocolMultiSelect } from "@/components/ui/protocol-multi-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
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
  credentialLabel,
  defaultProtocolConfigName,
  formBaseUrlsForPayload,
  FormProtocolConfig,
  FormState,
  HeaderItem,
  classifyModelQueryInput,
  isValidModelQueryRegex,
  Locale,
  protocolConfigCredentialKeys,
  protocolConfigSelectedCredentialIds,
  resolveBaseUrlId,
} from "./shared";

type CredentialOption = {
  id: string;
  display_name: string;
  enabled: boolean;
  api_key: string;
};

function CredentialMultiSelect({
  value,
  options,
  locale,
  invalid,
  onChange,
}: {
  value: string[];
  options: CredentialOption[];
  locale: Locale;
  invalid: boolean;
  onChange: (next: string[]) => void;
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const optionById = new Map(options.map((item) => [item.id, item]));
  const selectedInOrder = [
    ...options.filter((item) => value.includes(item.id)).map((item) => item.id),
    ...value.filter((id) => !optionById.has(id)),
  ];
  const selectedOptions = selectedInOrder.map((id) => ({
    id,
    label:
      optionById.get(id)?.display_name ||
      (locale === "zh-CN" ? "未知密钥" : "Unknown key"),
    available:
      Boolean(optionById.get(id)?.enabled) &&
      Boolean(optionById.get(id)?.api_key.trim()),
  }));
  const normalizedSearchQuery = searchQuery.trim().toLowerCase();
  const filteredOptions = normalizedSearchQuery
    ? options.filter((item) =>
        [item.display_name, item.id].some((text) =>
          text.toLowerCase().includes(normalizedSearchQuery),
        ),
      )
    : options;
  const multiColumn = filteredOptions.length > 4;

  const toggle = (id: string) => {
    onChange(
      value.includes(id) ? value.filter((item) => item !== id) : [...value, id],
    );
  };

  return (
    <Popover
      onOpenChange={(open) => {
        if (!open) setSearchQuery("");
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          aria-invalid={invalid || undefined}
          className={cn(
            "w-full justify-between px-3 font-normal",
            selectedOptions.length === 0 && "text-muted-foreground",
          )}
        >
          {selectedOptions.length ? (
            <span className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden">
              {selectedOptions.slice(0, 2).map((item) => (
                <span
                  key={item.id}
                  className={cn(
                    "truncate text-xs",
                    item.available
                      ? "text-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  {item.label}
                </span>
              ))}
              {selectedOptions.length > 2 ? (
                <span className="shrink-0 text-xs text-muted-foreground">
                  +{selectedOptions.length - 2}
                </span>
              ) : null}
            </span>
          ) : (
            <span className="truncate">
              {locale === "zh-CN" ? "选择密钥" : "Select keys"}
            </span>
          )}
          <ChevronDown className="ml-1 size-3.5 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className={cn(
          "p-2",
          multiColumn
            ? "w-80"
            : "w-max min-w-[var(--radix-popover-trigger-width)]",
        )}
      >
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="h-8 pl-8"
            placeholder={locale === "zh-CN" ? "搜索密钥" : "Search keys"}
          />
        </div>
        {filteredOptions.length ? (
          <div className={cn("grid gap-1", multiColumn && "grid-cols-2")}>
            {filteredOptions.map((item) => {
              const checked = value.includes(item.id);
              const available = item.enabled && item.api_key.trim();
              const checkboxId = `credential-opt-${item.id}`;
              return (
                <div
                  key={item.id}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted"
                >
                  <Checkbox
                    id={checkboxId}
                    checked={checked}
                    onCheckedChange={() => toggle(item.id)}
                  />
                  <label
                    htmlFor={checkboxId}
                    className="min-w-0 flex-1 cursor-pointer truncate"
                  >
                    {item.display_name}
                  </label>
                  {!available ? (
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {locale === "zh-CN" ? "不可用" : "Unavailable"}
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="px-2 py-1.5 text-sm text-muted-foreground">
            {locale === "zh-CN" ? "没有匹配密钥" : "No matching keys"}
          </div>
        )}
        {selectedOptions.length ? (
          <div className="mt-2 flex items-center justify-between border-t pt-2 text-xs text-muted-foreground">
            <span>
              {locale === "zh-CN"
                ? `已选 ${selectedOptions.length} 个`
                : `${selectedOptions.length} selected`}
            </span>
            <button
              type="button"
              className="text-foreground hover:underline"
              onClick={() => onChange([])}
            >
              {locale === "zh-CN" ? "清空" : "Clear"}
            </button>
          </div>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

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
  onAddManualModel: (index: number) => void;
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
  const selectedCredentialIds =
    protocolConfigSelectedCredentialIds(protocolConfig);
  const selectedActiveCredentialIds = selectedCredentialIds.filter((id) =>
    activeCredentialIds.has(id),
  );
  const modelQueryInput = protocolConfig.manual_model_name.trim();
  const modelQueryKind = classifyModelQueryInput(modelQueryInput);
  const isRegexQuery = modelQueryKind === "regex";
  const validRegexQuery =
    !isRegexQuery || isValidModelQueryRegex(modelQueryInput);
  const addModelDisabled =
    selectedActiveCredentialIds.length === 0 ||
    modelQueryKind !== "plain" ||
    !protocolConfig.manual_protocols.length;
  const fetchModelsDisabled =
    fetchingProtocolConfigIndex === protocolConfigIndex ||
    !activeBaseUrlValue(form, protocolConfig).trim() ||
    selectedActiveCredentialIds.length === 0 ||
    !protocolConfig.manual_protocols.length ||
    modelQueryKind === "plain" ||
    !validRegexQuery;
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
            <FieldLabel>{locale === "zh-CN" ? "密钥" : "Key"}</FieldLabel>
            <CredentialMultiSelect
              value={selectedCredentialIds}
              options={credentialOptions}
              locale={locale}
              invalid={selectedActiveCredentialIds.length === 0}
              onChange={(next) => {
                const nextCredentialIdSet = new Set(next);
                const primaryCredentialId = next.includes(
                  protocolConfig.credential_id,
                )
                  ? protocolConfig.credential_id
                  : (next[0] ?? "");
                onUpdateProtocolConfig(protocolConfigIndex, {
                  credential_id: primaryCredentialId,
                  credential_ids: next,
                  models: protocolConfig.models.filter((model) =>
                    nextCredentialIdSet.has(model.credential_id),
                  ),
                });
              }}
            />
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
              aria-label={
                locale === "zh-CN" ? "组合设置" : "Combination settings"
              }
              title={locale === "zh-CN" ? "组合设置" : "Combination settings"}
              onClick={() => onOpenAdvanced(protocolConfigIndex)}
            >
              <Settings size={16} />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="text-destructive hover:text-destructive"
              aria-label={
                locale === "zh-CN" ? "删除组合" : "Delete combination"
              }
              title={locale === "zh-CN" ? "删除组合" : "Delete combination"}
              onClick={() => onRemoveProtocolConfig(protocolConfigIndex)}
            >
              <Trash2 size={16} />
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
              <span>{locale === "zh-CN" ? "模型操作" : "Model actions"}</span>
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
              ? "地址来源、密钥和协议重复"
              : "Duplicate Base URL, key, and protocols"}
          </div>
        ) : null}

        {protocolConfig.expanded ? (
          <div className="grid gap-3 pt-1">
            <Separator />
            <FieldGroup className="gap-3">
              <div className="grid min-w-0 gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(180px,0.42fr)_auto_auto] lg:items-end">
                <Field data-invalid={isRegexQuery && !validRegexQuery}>
                  <FieldLabel>
                    {locale === "zh-CN" ? "模型名称" : "Model name"}
                  </FieldLabel>
                  <Input
                    className="w-full min-w-0"
                    value={protocolConfig.manual_model_name}
                    aria-invalid={isRegexQuery && !validRegexQuery}
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      const nextKind = classifyModelQueryInput(nextValue);
                      onUpdateProtocolConfig(protocolConfigIndex, {
                        manual_model_name: nextValue,
                        match_regex: nextKind === "plain" ? "" : nextValue,
                        auto_sync_enabled:
                          nextKind === "regex"
                            ? protocolConfig.auto_sync_enabled
                            : false,
                      });
                    }}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter" || addModelDisabled) return;
                      event.preventDefault();
                      onAddManualModel(protocolConfigIndex);
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
                    onChange={(next) =>
                      onUpdateProtocolConfig(protocolConfigIndex, {
                        manual_protocols: next,
                      })
                    }
                    locale={locale}
                    invalid={protocolConfig.manual_protocols.length === 0}
                  />
                </Field>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => onAddManualModel(protocolConfigIndex)}
                  disabled={addModelDisabled}
                >
                  <Plus data-icon="inline-start" />
                  {locale === "zh-CN" ? "添加模型" : "Add model"}
                </Button>
                <Button
                  type="button"
                  onClick={() => onFetchModels(protocolConfigIndex)}
                  disabled={fetchModelsDisabled}
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
                      onUpdateProtocolConfig(protocolConfigIndex, {
                        auto_sync_enabled: checked,
                        match_regex: protocolConfig.manual_model_name,
                      })
                    }
                    disabled={!validRegexQuery}
                  />
                </div>
              ) : null}
            </FieldGroup>
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
