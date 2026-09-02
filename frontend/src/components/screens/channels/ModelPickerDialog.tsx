import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import type { ProtocolKind } from "@/lib/api/protocols";
import { cn } from "@/lib/classNames";
import {
  genericModelKey,
  groupPickerModelsByName,
  hasPickerModelProtocolOverride,
  resolvePickerModelProtocols,
} from "./channelModelUtils";
import type { Locale, PickerModelItem } from "./channelTypes";
import { ProtocolMultiSelect } from "./ProtocolMultiSelect";

type PickerModelGroup = ReturnType<typeof groupPickerModelsByName>[number];

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
  const [expandedModelNames, setExpandedModelNames] = useState<string[]>([]);
  const modelGroups = useMemo(
    () => groupPickerModelsByName(availableModels),
    [availableModels],
  );
  const lowerModelSearchQuery = modelSearchQuery.trim().toLowerCase();
  const filteredModelGroups = useMemo(() => {
    if (!lowerModelSearchQuery) return modelGroups;
    return modelGroups.filter((group) =>
      [
        group.model_name,
        ...group.items.map((item) => item.credential_name ?? ""),
      ].some((value) => value.toLowerCase().includes(lowerModelSearchQuery)),
    );
  }, [modelGroups, lowerModelSearchQuery]);
  const searchTargetsModels = lowerModelSearchQuery.length > 0;
  const toggleGroupExpanded = (modelName: string) => {
    setExpandedModelNames((current) =>
      current.includes(modelName)
        ? current.filter((name) => name !== modelName)
        : [...current, modelName],
    );
  };
  const effectiveModelProtocols = (modelName: string) =>
    resolvePickerModelProtocols(
      modelName,
      pickerModelProtocols,
      pickerImportProtocols,
    );
  const sameProtocols = (left: ProtocolKind[], right: ProtocolKind[]) =>
    left.length === right.length && left.every((item) => right.includes(item));
  const toolbarProtocols =
    searchTargetsModels && filteredModelGroups.length
      ? (() => {
          const first = effectiveModelProtocols(
            filteredModelGroups[0].model_name,
          );
          return filteredModelGroups.every((group) =>
            sameProtocols(first, effectiveModelProtocols(group.model_name)),
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
      filteredModelGroups.map((group) => group.model_name),
      protocols,
    );
  };
  const selectionLabel = locale === "zh-CN" ? "选择模型" : "Select model";

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
                    {locale === "zh-CN" ? "上游协议" : "Upstream protocols"}
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
                          ? "上游协议"
                          : "Upstream protocols"
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
                  {filteredModelGroups.map((group) => (
                    <PickerGroupRow
                      key={group.model_name}
                      group={group}
                      locale={locale}
                      selectionLabel={selectionLabel}
                      isExpanded={expandedModelNames.includes(group.model_name)}
                      onToggleExpanded={() =>
                        toggleGroupExpanded(group.model_name)
                      }
                      selectedKeys={pickerSelectedModelKeys}
                      protocols={effectiveModelProtocols(group.model_name)}
                      overridden={hasPickerModelProtocolOverride(
                        pickerModelProtocols,
                        group.model_name,
                      )}
                      onToggleModel={onToggleModel}
                      onModelProtocolsChange={(next) =>
                        onFilteredModelProtocolsChange([group.model_name], next)
                      }
                    />
                  ))}
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
                    filteredModelGroups.map((group) => group.model_name),
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

function PickerGroupRow({
  group,
  locale,
  selectionLabel,
  isExpanded,
  onToggleExpanded,
  selectedKeys,
  protocols,
  overridden,
  onToggleModel,
  onModelProtocolsChange,
}: {
  group: PickerModelGroup;
  locale: Locale;
  selectionLabel: string;
  isExpanded: boolean;
  onToggleExpanded: () => void;
  selectedKeys: string[];
  protocols: ProtocolKind[];
  overridden: boolean;
  onToggleModel: (key: string) => void;
  onModelProtocolsChange: (protocols: ProtocolKind[]) => void;
}) {
  const isMultiKey = group.items.length > 1;
  const groupChecked = selectedKeys.includes(group.model_name);
  const selectedMemberCount = group.items.filter((item) =>
    selectedKeys.includes(genericModelKey(item)),
  ).length;
  return (
    <div className={cn("px-1 py-2", groupChecked && "bg-primary/5")}>
      <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
        <div className="flex min-w-0 items-center gap-3 rounded-md px-1.5 py-1.5 transition-colors hover:bg-muted/50">
          {isMultiKey ? (
            <Checkbox
              checked={
                selectedMemberCount === 0
                  ? groupChecked
                  : selectedMemberCount === group.items.length
                    ? true
                    : "indeterminate"
              }
              onCheckedChange={() => onToggleModel(group.model_name)}
              aria-label={selectionLabel}
            />
          ) : (
            <Checkbox
              checked={groupChecked || selectedMemberCount === 1}
              onCheckedChange={() =>
                onToggleModel(
                  groupChecked
                    ? group.model_name
                    : genericModelKey(group.items[0]),
                )
              }
              aria-label={selectionLabel}
            />
          )}
          <button
            type="button"
            className="min-w-0 flex-1 text-left"
            onClick={() => onToggleModel(group.model_name)}
          >
            <span
              className={cn(
                "block truncate text-sm text-foreground",
                (groupChecked || selectedMemberCount > 0) && "font-medium",
              )}
            >
              {group.model_name}
            </span>
            {isMultiKey ? (
              <span className="block truncate text-xs text-muted-foreground">
                {locale === "zh-CN"
                  ? `${group.items.length} 个密钥`
                  : `${group.items.length} keys`}
                {selectedMemberCount > 0 && !groupChecked
                  ? locale === "zh-CN"
                    ? ` · 已选 ${selectedMemberCount}`
                    : ` · ${selectedMemberCount} selected`
                  : ""}
              </span>
            ) : (
              group.items[0].credential_name && (
                <span className="block truncate text-xs text-muted-foreground">
                  {group.items[0].credential_name}
                </span>
              )
            )}
          </button>
          {isMultiKey ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="text-muted-foreground"
              aria-label={
                locale === "zh-CN" ? "展开密钥明细" : "Expand key details"
              }
              title={locale === "zh-CN" ? "展开密钥明细" : "Expand key details"}
              onClick={onToggleExpanded}
            >
              <ChevronDown
                className={cn(
                  "transition-transform",
                  isExpanded && "rotate-180",
                )}
              />
            </Button>
          ) : null}
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
            onChange={onModelProtocolsChange}
            locale={locale}
            invalid={
              (groupChecked || selectedMemberCount > 0) &&
              protocols.length === 0
            }
            className="h-8 max-w-full sm:max-w-52"
            placeholder={locale === "zh-CN" ? "继承本次协议" : "Inherit import"}
          />
        </div>
      </div>
      {isMultiKey && isExpanded ? (
        <div className="mt-1 mb-1 ml-7 flex flex-col divide-y">
          {group.items.map((item) => {
            const memberKey = genericModelKey(item);
            const memberChecked = selectedKeys.includes(memberKey);
            return (
              <div
                key={memberKey}
                className={cn(
                  "flex min-w-0 items-center gap-3 py-1.5",
                  memberChecked && "text-foreground",
                )}
              >
                <Checkbox
                  checked={memberChecked}
                  onCheckedChange={() => onToggleModel(memberKey)}
                  aria-label={selectionLabel}
                />
                <button
                  type="button"
                  className={cn(
                    "min-w-0 flex-1 truncate text-left text-xs",
                    memberChecked
                      ? "font-medium text-foreground"
                      : "text-muted-foreground",
                  )}
                  onClick={() => onToggleModel(memberKey)}
                >
                  {item.credential_name?.trim() || memberKey}
                </button>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
