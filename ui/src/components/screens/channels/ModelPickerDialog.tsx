"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { ProtocolMultiSelect } from "@/components/ui/ProtocolMultiSelect";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import type { ProtocolKind } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  genericModelKey,
  groupPickerModels,
  hasPickerModelProtocolOverride,
  resolvePickerModelProtocols,
  type Locale,
  type PickerModelItem,
} from "./channelShared";

/** Renders the searchable model picker for a protocol configuration. */
export function ModelPickerDialog({
  open,
  availableModels,
  pickerSelectedModelKeys,
  pickerImportProtocols,
  pickerModelProtocols,
  locale,
  onOpenChange,
  onToggleModel,
  onImportProtocolsChange,
  onFilteredModelProtocolsChange,
  onConfirm,
  onConfirmAll,
  onCancel,
}: {
  open: boolean;
  availableModels: PickerModelItem[];
  pickerSelectedModelKeys: string[];
  pickerImportProtocols: ProtocolKind[];
  pickerModelProtocols: Record<string, ProtocolKind[]>;
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onToggleModel: (key: string) => void;
  onImportProtocolsChange: (protocols: ProtocolKind[]) => void;
  onFilteredModelProtocolsChange: (
    keys: string[],
    protocols: ProtocolKind[],
  ) => void;
  onConfirm: () => void;
  onConfirmAll: (keys: string[]) => void;
  onCancel: () => void;
}) {
  const [modelSearchQuery, setModelSearchQuery] = useState("");
  const modelGroups = useMemo(
    () => groupPickerModels(availableModels),
    [availableModels],
  );
  const normalizedModelSearch = modelSearchQuery.trim().toLowerCase();
  const filteredModelGroups = useMemo(() => {
    if (!normalizedModelSearch) return modelGroups;
    return modelGroups.filter((model) =>
      [model.model_name, model.credential_name ?? ""].some((value) =>
        value.toLowerCase().includes(normalizedModelSearch),
      ),
    );
  }, [modelGroups, normalizedModelSearch]);
  const searchTargetsModels = normalizedModelSearch.length > 0;
  const effectiveModelProtocols = (key: string) => {
    return resolvePickerModelProtocols(
      key,
      pickerModelProtocols,
      pickerImportProtocols,
    );
  };
  const sameProtocols = (left: ProtocolKind[], right: ProtocolKind[]) =>
    left.length === right.length && left.every((item) => right.includes(item));
  const toolbarProtocols =
    searchTargetsModels && filteredModelGroups.length
      ? (() => {
          const first = effectiveModelProtocols(
            genericModelKey(filteredModelGroups[0]),
          );
          return filteredModelGroups.every((model) =>
            sameProtocols(
              first,
              effectiveModelProtocols(genericModelKey(model)),
            ),
          )
            ? first
            : [];
        })()
      : pickerImportProtocols;
  const changeToolbarProtocols = (protocols: ProtocolKind[]) => {
    if (!searchTargetsModels) {
      onImportProtocolsChange(protocols);
      return;
    }
    onFilteredModelProtocolsChange(
      filteredModelGroups.map((model) => genericModelKey(model)),
      protocols,
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <AppDialogContent
          className="max-w-3xl"
          title={locale === "zh-CN" ? "选择模型" : "Select models"}
        >
          <div className="grid gap-4 pt-2">
            <div className="space-y-2 border-b pb-3">
              <div className="grid gap-2 sm:grid-cols-[minmax(18rem,1fr)_minmax(14rem,auto)] sm:items-center">
                <ToolbarSearchInput
                  value={modelSearchQuery}
                  onChange={setModelSearchQuery}
                  onClear={() => setModelSearchQuery("")}
                  placeholder={
                    locale === "zh-CN"
                      ? "搜索模型或密钥"
                      : "Search models or keys"
                  }
                  className="max-w-none"
                />
                <div className="flex min-w-0 items-center gap-2 sm:justify-end">
                  <span className="shrink-0 text-xs font-medium text-muted-foreground">
                    {locale === "zh-CN" ? "客户端协议" : "Client protocols"}
                  </span>
                  <ProtocolMultiSelect
                    value={toolbarProtocols}
                    onChange={changeToolbarProtocols}
                    locale={locale}
                    disabled={
                      searchTargetsModels && !filteredModelGroups.length
                    }
                    className="h-8 max-w-full"
                    placeholder={
                      searchTargetsModels
                        ? locale === "zh-CN"
                          ? "设置匹配协议"
                          : "Set matched"
                        : locale === "zh-CN"
                          ? "客户端协议"
                          : "Client protocols"
                    }
                  />
                </div>
              </div>
              <div className="text-xs text-muted-foreground">
                <span>
                  {searchTargetsModels
                    ? locale === "zh-CN"
                      ? `找到 ${filteredModelGroups.length}/${modelGroups.length} 个模型`
                      : `${filteredModelGroups.length}/${modelGroups.length} matched`
                    : locale === "zh-CN"
                      ? `找到 ${modelGroups.length} 个模型`
                      : `${modelGroups.length} models`}
                </span>
              </div>
            </div>
            <div className="max-h-[58dvh] overflow-y-auto sm:max-h-[420px]">
              {filteredModelGroups.length ? (
                <div className="flex w-full flex-col divide-y">
                  {filteredModelGroups.map((model) => {
                    const key = genericModelKey(model);
                    const checked = pickerSelectedModelKeys.includes(key);
                    const protocols = effectiveModelProtocols(key);
                    const overridden = hasPickerModelProtocolOverride(
                      pickerModelProtocols,
                      key,
                    );
                    return (
                      <div
                        key={key}
                        className={cn(
                          "grid min-w-0 gap-2 px-1 py-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center",
                          checked && "bg-primary/5",
                        )}
                      >
                        <div className="flex min-w-0 items-center gap-3 rounded-md px-1.5 py-1.5 transition-colors hover:bg-muted/50">
                          <Checkbox
                            checked={checked}
                            onCheckedChange={() => onToggleModel(key)}
                            aria-label={
                              locale === "zh-CN" ? "选择模型" : "Select model"
                            }
                          />
                          <button
                            type="button"
                            className="min-w-0 flex-1 text-left"
                            onClick={() => onToggleModel(key)}
                          >
                            <span
                              className={cn(
                                "block truncate text-sm text-foreground",
                                checked && "font-medium",
                              )}
                            >
                              {model.model_name}
                            </span>
                            {model.credential_name ? (
                              <span className="block truncate text-xs text-muted-foreground">
                                {model.credential_name}
                              </span>
                            ) : null}
                          </button>
                        </div>
                        <div className="flex min-w-0 items-center gap-2 pl-8 sm:justify-end sm:pl-0">
                          {overridden ? (
                            <span className="shrink-0 text-xs text-foreground">
                              {locale === "zh-CN" ? "覆盖" : "Override"}
                            </span>
                          ) : (
                            <span className="shrink-0 text-xs text-muted-foreground">
                              {locale === "zh-CN" ? "继承" : "Inherit"}
                            </span>
                          )}
                          <ProtocolMultiSelect
                            value={protocols}
                            onChange={(next) =>
                              onFilteredModelProtocolsChange([key], next)
                            }
                            locale={locale}
                            invalid={checked && protocols.length === 0}
                            className="h-8 max-w-full sm:max-w-52"
                            placeholder={
                              locale === "zh-CN"
                                ? "继承本次协议"
                                : "Inherit import"
                            }
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="px-3 py-8 text-sm text-muted-foreground">
                  {locale === "zh-CN"
                    ? searchTargetsModels
                      ? "没有匹配的模型"
                      : "未获取到可选模型"
                    : searchTargetsModels
                      ? "No matching models."
                      : "No models fetched."}
                </div>
              )}
            </div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button type="button" variant="outline" onClick={onCancel}>
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  onConfirmAll(
                    filteredModelGroups.map((model) => genericModelKey(model)),
                  )
                }
                disabled={!filteredModelGroups.length}
              >
                {searchTargetsModels
                  ? locale === "zh-CN"
                    ? "加入匹配模型"
                    : "Add matched models"
                  : locale === "zh-CN"
                    ? "加入全部模型"
                    : "Add all models"}
              </Button>
              <Button
                type="button"
                onClick={onConfirm}
                disabled={!pickerSelectedModelKeys.length}
              >
                {locale === "zh-CN" ? "加入模型" : "Add models"}
              </Button>
            </div>
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}
