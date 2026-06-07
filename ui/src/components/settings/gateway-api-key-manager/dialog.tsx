"use client";

import { startTransition, useEffect, useState } from "react";
import { enUS, zhCN } from "date-fns/locale";
import { ChevronsUpDown } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { AppDialogContent, Dialog, DialogFooter } from "@/components/ui/dialog";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { ApiError, type GatewayApiKey, apiRequest } from "@/lib/api";
import type { Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import {
  formatDateLabel,
  protocolSummary,
  titleForLocale,
  toGatewayApiKeyForm,
  toGatewayApiKeyPayload,
  type GatewayApiKeyForm,
  type GatewayModelGroupOption,
} from "./shared";

export type GatewayApiKeyDialogProps = {
  locale: Locale;
  open: boolean;
  editingKey: GatewayApiKey | null;
  modelGroupOptions: GatewayModelGroupOption[];
  timeZone: string;
  onClose: () => void;
  onSaved: () => Promise<void>;
};

export function GatewayApiKeyDialog({
  locale,
  open,
  editingKey,
  modelGroupOptions,
  timeZone,
  onClose,
  onSaved,
}: GatewayApiKeyDialogProps) {
  const [form, setForm] = useState<GatewayApiKeyForm>(() =>
    toGatewayApiKeyForm(editingKey ?? undefined, timeZone),
  );
  const [submitting, setSubmitting] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(toGatewayApiKeyForm(editingKey ?? undefined, timeZone));
      setPickerOpen(false);
    }
  }, [open, editingKey, timeZone]);

  const editingKeyId = editingKey?.id ?? null;

  const permissionSummary = !form.restrictModels
    ? titleForLocale(locale, "全部当前模型组", "All current model groups")
    : form.allowedModels.length > 0
      ? form.allowedModels.join(", ")
      : titleForLocale(locale, "请选择模型组", "Select model groups");

  function updateForm<K extends keyof GatewayApiKeyForm>(
    key: K,
    value: GatewayApiKeyForm[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function toggleAllowedModel(name: string) {
    startTransition(() => {
      setForm((current) => {
        const exists = current.allowedModels.includes(name);
        return {
          ...current,
          allowedModels: exists
            ? current.allowedModels.filter((item) => item !== name)
            : [...current.allowedModels, name].sort((left, right) =>
                left.localeCompare(right),
              ),
        };
      });
    });
  }

  async function submit() {
    if (form.restrictModels && form.allowedModels.length === 0) {
      toast.error(
        titleForLocale(
          locale,
          "至少选择一个模型组",
          "Select at least one model group",
        ),
      );
      return;
    }
    setSubmitting(true);
    try {
      const payload = toGatewayApiKeyPayload(form, timeZone);
      if (editingKeyId) {
        await apiRequest<GatewayApiKey>(
          `/admin/gateway-api-keys/${editingKeyId}`,
          {
            method: "PUT",
            body: JSON.stringify(payload),
          },
        );
      } else {
        await apiRequest<GatewayApiKey>("/admin/gateway-api-keys", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      toast.success(
        titleForLocale(
          locale,
          editingKeyId ? "API Key 已更新" : "API Key 已创建",
          editingKeyId ? "API key updated" : "API key created",
        ),
      );
      onClose();
      await onSaved();
    } catch (requestError) {
      const message =
        requestError instanceof ApiError
          ? requestError.message
          : titleForLocale(
              locale,
              editingKeyId ? "更新 API Key 失败" : "创建 API Key 失败",
              editingKeyId
                ? "Failed to update API key"
                : "Failed to create API key",
            );
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setPickerOpen(false);
          onClose();
        }
      }}
    >
      <AppDialogContent
        className="sm:max-w-xl"
        title={titleForLocale(
          locale,
          editingKeyId ? "编辑 API Key" : "创建 API Key",
          editingKeyId ? "Edit API key" : "Create API key",
        )}
      >
        <div className="flex flex-col gap-4">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="gateway-key-remark">
                {titleForLocale(locale, "密钥名称", "Key name")}
              </FieldLabel>
              <Input
                id="gateway-key-remark"
                value={form.remark}
                onChange={(event) => updateForm("remark", event.target.value)}
                placeholder={titleForLocale(locale, "可留空", "Optional")}
              />
            </Field>

            <Field
              orientation="horizontal"
              className="items-center justify-between rounded-lg border bg-muted/20 px-3 py-3"
            >
              <FieldContent>
                <FieldLabel className="w-auto">
                  {titleForLocale(locale, "启用", "Enabled")}
                </FieldLabel>
                <FieldDescription>
                  {titleForLocale(
                    locale,
                    "关闭后立即拒绝该密钥请求",
                    "Reject requests immediately when disabled",
                  )}
                </FieldDescription>
              </FieldContent>
              <Switch
                checked={form.enabled}
                onCheckedChange={(checked) =>
                  updateForm("enabled", Boolean(checked))
                }
              />
            </Field>

            <Field>
              <FieldLabel htmlFor="gateway-key-limit">
                {titleForLocale(locale, "最大余额 (USD)", "Max balance (USD)")}
              </FieldLabel>
              <Input
                id="gateway-key-limit"
                type="number"
                min="0"
                step="0.0001"
                value={form.maxCostUsd}
                onChange={(event) =>
                  updateForm("maxCostUsd", event.target.value)
                }
              />
              <FieldDescription>
                {titleForLocale(
                  locale,
                  "填 0 表示不限制",
                  "Use 0 for unlimited",
                )}
              </FieldDescription>
            </Field>

            <FieldSet>
              <FieldLegend variant="label">
                {titleForLocale(locale, "允许模型组", "Allowed model groups")}
              </FieldLegend>

              <Field
                orientation="horizontal"
                className="items-center justify-between rounded-lg border bg-muted/20 px-3 py-3"
              >
                <FieldContent>
                  <FieldLabel className="w-auto">
                    {titleForLocale(
                      locale,
                      "仅允许选定模型组",
                      "Restrict to selected groups",
                    )}
                  </FieldLabel>
                  <FieldDescription>
                    {titleForLocale(
                      locale,
                      "关闭时可调用当前全部启用模型组",
                      "Disabled means the key can use every enabled model group",
                    )}
                  </FieldDescription>
                </FieldContent>
                <Switch
                  checked={form.restrictModels}
                  onCheckedChange={(checked) => {
                    startTransition(() => {
                      setForm((current) => ({
                        ...current,
                        restrictModels: Boolean(checked),
                      }));
                    });
                  }}
                />
              </Field>

              <Field data-disabled={!form.restrictModels}>
                <FieldLabel>
                  {titleForLocale(locale, "模型组", "Model groups")}
                </FieldLabel>
                <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      className="w-full justify-between"
                      disabled={!form.restrictModels}
                    >
                      <span className="truncate text-left">
                        {permissionSummary}
                      </span>
                      <ChevronsUpDown className="text-muted-foreground" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent
                    align="start"
                    className="w-[calc(100vw-2rem)] p-0 sm:w-[360px]"
                  >
                    <Command>
                      <CommandInput
                        placeholder={titleForLocale(
                          locale,
                          "搜索模型组...",
                          "Search model groups...",
                        )}
                      />
                      <CommandList>
                        <CommandEmpty>
                          {modelGroupOptions.length > 0
                            ? titleForLocale(
                                locale,
                                "没有匹配的模型组",
                                "No matching model groups",
                              )
                            : titleForLocale(
                                locale,
                                "当前没有可用模型组",
                                "No model groups available",
                              )}
                        </CommandEmpty>
                        <CommandGroup
                          heading={titleForLocale(
                            locale,
                            "当前启用模型组",
                            "Enabled model groups",
                          )}
                        >
                          {modelGroupOptions.map((option) => {
                            const checked = form.allowedModels.includes(
                              option.name,
                            );
                            return (
                              <CommandItem
                                key={option.name}
                                value={`${option.name} ${protocolSummary(locale, option.protocols)} ${option.channelNames.join(" ")}`}
                                onSelect={() => toggleAllowedModel(option.name)}
                                className="items-start gap-3"
                              >
                                <Checkbox
                                  checked={checked}
                                  className="mt-0.5 pointer-events-none"
                                />
                                <div className="min-w-0 flex-1">
                                  <div className="truncate font-medium text-foreground">
                                    {option.name}
                                  </div>
                                  <div className="truncate text-xs text-muted-foreground">
                                    {protocolSummary(locale, option.protocols)}{" "}
                                    ·{" "}
                                    {titleForLocale(
                                      locale,
                                      `${option.enabledItemCount} 个启用成员`,
                                      `${option.enabledItemCount} enabled members`,
                                    )}
                                  </div>
                                </div>
                              </CommandItem>
                            );
                          })}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
                <FieldDescription>
                  {form.restrictModels
                    ? titleForLocale(
                        locale,
                        "权限来源于当前启用模型组；留空将无法保存",
                        "Permissions come from currently enabled model groups; choose at least one",
                      )
                    : titleForLocale(
                        locale,
                        "当前为全部放行模式",
                        "The key can currently access all model groups",
                      )}
                </FieldDescription>
                {form.restrictModels && form.allowedModels.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {form.allowedModels.map((modelName) => (
                      <Badge key={modelName} variant="outline">
                        {modelName}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </Field>
            </FieldSet>

            <Field>
              <FieldLabel>
                {titleForLocale(locale, "过期日期", "Expires on")}
              </FieldLabel>
              <div className="flex flex-col gap-3 md:flex-row">
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      className={cn(
                        "w-full justify-between md:flex-1",
                        !form.expiresOn && "text-muted-foreground",
                      )}
                    >
                      <span>{formatDateLabel(locale, form.expiresOn)}</span>
                      <ChevronsUpDown className="text-muted-foreground" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent
                    align="start"
                    className="w-auto overflow-hidden p-0"
                  >
                    <Calendar
                      mode="single"
                      selected={form.expiresOn}
                      defaultMonth={form.expiresOn}
                      onSelect={(value) =>
                        updateForm("expiresOn", value ?? undefined)
                      }
                      locale={locale === "zh-CN" ? zhCN : enUS}
                      captionLayout="dropdown"
                    />
                  </PopoverContent>
                </Popover>

                <Button
                  type="button"
                  variant="outline"
                  onClick={() => updateForm("expiresOn", undefined)}
                >
                  {titleForLocale(locale, "清空", "Clear")}
                </Button>
              </div>
              <FieldDescription>
                {titleForLocale(
                  locale,
                  "留空表示永不过期",
                  "Leave blank to keep the key active forever",
                )}
              </FieldDescription>
            </Field>
          </FieldGroup>

          <DialogFooter className="mx-0 mb-0 rounded-none border-0 bg-transparent p-0 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              {titleForLocale(locale, "取消", "Cancel")}
            </Button>
            <Button
              type="button"
              onClick={() => void submit()}
              disabled={submitting}
            >
              {submitting
                ? titleForLocale(locale, "保存中...", "Saving...")
                : titleForLocale(locale, "保存", "Save")}
            </Button>
          </DialogFooter>
        </div>
      </AppDialogContent>
    </Dialog>
  );
}
