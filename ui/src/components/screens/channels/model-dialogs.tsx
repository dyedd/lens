"use client";

import { useMemo, useState } from "react";
import type { KeyboardEvent } from "react";
import { Check, ChevronsUpDown, RefreshCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { AppDialogContent, Dialog } from "@/components/ui/dialog";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type {
  ModelGroup,
  ModelGroupEnsureFromSiteResponse,
  ModelGroupEnsureResultItem,
  ModelGroupEnsureStatus,
  ProtocolKind,
  SiteModelTestResult,
} from "@/lib/api";
import {
  activeBaseUrlValue,
  BatchModelTestOption,
  BatchModelTestRow,
  batchTestStatusLabel,
  batchTestStatusVariant,
  compactProtocolLabel,
  credentialLabel,
  FormState,
  genericModelKey,
  groupPickerModels,
  Locale,
  ModelTestTarget,
  modelBadgeClassName,
  modelSupportedProtocols,
  PickerModelItem,
  protocolBadgeClassName,
  protocolLabel,
  selectClassName,
  selectedModelTestProtocol,
} from "./shared";
import {
  canSubmitModelGroupEnsureItem,
  executionModelGroups,
  modelGroupEnsureReasonLabel,
  modelGroupEnsureResultKey,
  selectableModelGroupsForEnsureItem,
} from "./model-group-ensure";

function modelGroupEnsureStatusLabel(
  status: ModelGroupEnsureStatus,
  locale: Locale,
) {
  if (status === "create") return locale === "zh-CN" ? "新建" : "Create";
  if (status === "update") return locale === "zh-CN" ? "加入" : "Update";
  if (status === "unchanged")
    return locale === "zh-CN" ? "已存在" : "Unchanged";
  return locale === "zh-CN" ? "跳过" : "Skipped";
}

function modelGroupEnsureStatusVariant(
  status: ModelGroupEnsureStatus,
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "create") return "default";
  if (status === "update") return "secondary";
  if (status === "skipped") return "destructive";
  return "outline";
}

function nextCreateModelGroupName(
  modelName: string,
  modelGroups: ModelGroup[],
) {
  const groupNames = new Set(modelGroups.map((group) => group.name));
  if (!groupNames.has(modelName)) return modelName;
  for (let index = 1; ; index += 1) {
    const candidate = `${modelName}-${index}`;
    if (!groupNames.has(candidate)) return candidate;
  }
}

export function ModelGroupEnsureDialog({
  open,
  locale,
  result,
  modelGroups,
  selectedItemKeys,
  allowProtocolExtension,
  confirming,
  onOpenChange,
  onToggleItem,
  onAllowProtocolExtensionChange,
  onTargetGroupChange,
  onConfirm,
}: {
  open: boolean;
  locale: Locale;
  result: ModelGroupEnsureFromSiteResponse | null;
  modelGroups: ModelGroup[];
  selectedItemKeys: string[];
  allowProtocolExtension: boolean;
  confirming: boolean;
  onOpenChange: (open: boolean) => void;
  onToggleItem: (item: ModelGroupEnsureResultItem) => void;
  onAllowProtocolExtensionChange: (allowed: boolean) => void;
  onTargetGroupChange: (
    item: ModelGroupEnsureResultItem,
    groupName: string,
  ) => void;
  onConfirm: (groupNameOverrides?: Record<string, string>) => void;
}) {
  const [createGroupNameDrafts, setCreateGroupNameDrafts] = useState<
    Record<string, string>
  >({});
  const [createGroupNameErrors, setCreateGroupNameErrors] = useState<
    Record<string, string>
  >({});
  const [openTargetGroupKey, setOpenTargetGroupKey] = useState<string | null>(
    null,
  );
  const requiresProtocolExtension = Boolean(
    result?.items.some(
      (item) =>
        item.skipped_reason === "protocol_extension_required" ||
        item.missing_protocols.length > 0,
    ),
  );
  const missingProtocolLabels = Array.from(
    new Set(
      result?.items.flatMap((item) =>
        item.missing_protocols.map(compactProtocolLabel),
      ) ?? [],
    ),
  );
  const selectedCount =
    result?.items.filter(
      (item) =>
        canSubmitModelGroupEnsureItem(item) &&
        selectedItemKeys.includes(modelGroupEnsureResultKey(item)),
    ).length ?? 0;
  const hasInvalidSelectedCreateName =
    result?.items.some((item) => {
      const key = modelGroupEnsureResultKey(item);
      const selected = selectedItemKeys.includes(key);
      if (!selected || !canSubmitModelGroupEnsureItem(item)) return false;
      const targetModelGroups = selectableModelGroupsForEnsureItem(
        item,
        modelGroups,
        allowProtocolExtension,
      );
      const targetGroupExists = targetModelGroups.some(
        (group) => group.name === item.group_name,
      );
      if (targetGroupExists) return false;

      const createName = createGroupNameForItem(
        item,
        key,
        targetGroupExists,
      ).trim();
      if (!createName) return true;

      const matchedGroup = executionModelGroups(modelGroups).find(
        (g) => g.name === createName,
      );
      return Boolean(matchedGroup);
    }) ?? false;

  function createGroupNameForItem(
    item: ModelGroupEnsureResultItem,
    key: string,
    targetGroupIsSelectable: boolean,
  ) {
    return (
      createGroupNameDrafts[key] ??
      (targetGroupIsSelectable
        ? item.group_name
        : nextCreateModelGroupName(item.model_name, modelGroups))
    );
  }

  function commitCreateGroupName(item: ModelGroupEnsureResultItem) {
    const key = modelGroupEnsureResultKey(item);
    const nextGroupName = createGroupNameDrafts[key]?.trim();
    if (!nextGroupName) return;

    const matchedGroup = executionModelGroups(modelGroups).find(
      (g) => g.name === nextGroupName,
    );
    if (matchedGroup) {
      setCreateGroupNameErrors((current) => ({
        ...current,
        [key]:
          locale === "zh-CN"
            ? "同名组已存在，请使用其他名称。"
            : "Name already exists, choose another.",
      }));
      return;
    }

    setCreateGroupNameErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });

    setCreateGroupNameDrafts((current) => ({
      ...current,
      [key]: nextGroupName,
    }));
    if (nextGroupName !== item.group_name) {
      onTargetGroupChange(item, nextGroupName);
    }
  }

  function confirmWithDrafts() {
    const overrides: Record<string, string> = {};
    for (const [key, value] of Object.entries(createGroupNameDrafts)) {
      const groupName = value.trim();
      if (groupName) overrides[key] = groupName;
    }
    onConfirm(overrides);
  }

  function handleCreateNameKeyDown(
    event: KeyboardEvent<HTMLInputElement>,
    item: ModelGroupEnsureResultItem,
  ) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    commitCreateGroupName(item);
  }

  function selectCreateTarget(item: ModelGroupEnsureResultItem, key: string) {
    const nextGroupName = nextCreateModelGroupName(
      item.model_name,
      modelGroups,
    );
    setCreateGroupNameErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setCreateGroupNameDrafts((current) => ({
      ...current,
      [key]: nextGroupName,
    }));
    setOpenTargetGroupKey(null);
    onTargetGroupChange(item, nextGroupName);
  }

  function selectExistingTarget(
    item: ModelGroupEnsureResultItem,
    key: string,
    groupName: string,
  ) {
    setCreateGroupNameErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setCreateGroupNameDrafts((current) => ({
      ...current,
      [key]: groupName,
    }));
    setOpenTargetGroupKey(null);
    onTargetGroupChange(item, groupName);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && confirming) return;
        onOpenChange(nextOpen);
      }}
    >
      {open && result ? (
        <AppDialogContent
          className="max-w-5xl"
          title={locale === "zh-CN" ? "加入/创建模型组" : "Add/create groups"}
        >
          <div className="grid gap-4">
            <div className="flex flex-wrap gap-2 rounded-md border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
              <span>
                {locale === "zh-CN"
                  ? `新建 ${result.created_count}`
                  : `Create ${result.created_count}`}
              </span>
              <span>
                {locale === "zh-CN"
                  ? `加入 ${result.updated_count}`
                  : `Update ${result.updated_count}`}
              </span>
              <span>
                {locale === "zh-CN"
                  ? `已存在 ${result.unchanged_count}`
                  : `Unchanged ${result.unchanged_count}`}
              </span>
              <span>
                {locale === "zh-CN"
                  ? `跳过 ${result.skipped_count}`
                  : `Skipped ${result.skipped_count}`}
              </span>
            </div>

            {requiresProtocolExtension ? (
              <Field orientation="horizontal" className="items-center gap-3">
                <Checkbox
                  checked={allowProtocolExtension}
                  disabled={confirming}
                  aria-label={
                    locale === "zh-CN"
                      ? "允许扩展已有模型组协议"
                      : "Allow protocol extension"
                  }
                  onCheckedChange={(checked) =>
                    onAllowProtocolExtensionChange(Boolean(checked))
                  }
                />
                <div className="flex min-w-0 flex-col gap-1">
                  <FieldLabel className="w-auto">
                    {locale === "zh-CN"
                      ? "允许扩展已有模型组协议"
                      : "Allow protocol extension"}
                  </FieldLabel>
                  <FieldDescription>
                    {locale === "zh-CN"
                      ? `不修改已有组协议。以下协议现有组不包含，相关模型会被跳过：${missingProtocolLabels.join(", ")}`
                      : `Existing group protocols stay unchanged. Models using the following protocols will be skipped: ${missingProtocolLabels.join(", ")}`}
                  </FieldDescription>
                </div>
              </Field>
            ) : null}

            <div className="overflow-hidden rounded-md border">
              <div className="max-h-[52dvh] overflow-y-auto sm:max-h-[420px]">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10">
                        <span className="sr-only">
                          {locale === "zh-CN" ? "选择" : "Select"}
                        </span>
                      </TableHead>
                      <TableHead className="w-24">
                        {locale === "zh-CN" ? "状态" : "Status"}
                      </TableHead>
                      <TableHead className="w-[280px]">
                        {locale === "zh-CN" ? "模型" : "Model"}
                      </TableHead>
                      <TableHead className="w-[360px]">
                        {locale === "zh-CN" ? "目标模型组" : "Target group"}
                      </TableHead>
                      <TableHead className="w-44">
                        {locale === "zh-CN" ? "协议" : "Protocols"}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.items.map((item) => {
                      const key = modelGroupEnsureResultKey(item);
                      const executable = canSubmitModelGroupEnsureItem(item);
                      const selected = selectedItemKeys.includes(key);
                      const targetModelGroups =
                        selectableModelGroupsForEnsureItem(
                          item,
                          modelGroups,
                          allowProtocolExtension,
                        );
                      const targetGroupIsSelectable = targetModelGroups.some(
                        (group) => group.name === item.group_name,
                      );
                      const createGroupName = createGroupNameForItem(
                        item,
                        key,
                        targetGroupIsSelectable,
                      );
                      const createValue = "__create__";
                      const targetValue = targetGroupIsSelectable
                        ? item.group_name
                        : createValue;
                      return (
                        <TableRow key={key}>
                          <TableCell>
                            <Checkbox
                              checked={selected}
                              disabled={!executable || confirming}
                              aria-label={
                                locale === "zh-CN"
                                  ? `选择 ${item.group_name}`
                                  : `Select ${item.group_name}`
                              }
                              onCheckedChange={() => onToggleItem(item)}
                            />
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={modelGroupEnsureStatusVariant(
                                item.status,
                              )}
                            >
                              {modelGroupEnsureStatusLabel(item.status, locale)}
                            </Badge>
                          </TableCell>
                          <TableCell className="min-w-[220px] max-w-[300px]">
                            <div
                              className="truncate font-medium"
                              title={item.model_name}
                            >
                              {item.model_name}
                            </div>
                          </TableCell>
                          <TableCell className="min-w-[320px]">
                            <div className="flex max-w-[360px] flex-col gap-1.5">
                              <Popover
                                open={openTargetGroupKey === key}
                                onOpenChange={(nextOpen) =>
                                  setOpenTargetGroupKey(nextOpen ? key : null)
                                }
                              >
                                <PopoverTrigger asChild>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    disabled={confirming}
                                    role="combobox"
                                    aria-expanded={openTargetGroupKey === key}
                                    className="w-full justify-between"
                                  >
                                    <span className="truncate">
                                      {targetValue === createValue
                                        ? locale === "zh-CN"
                                          ? "新建模型组"
                                          : "Create group"
                                        : item.group_name}
                                    </span>
                                    <ChevronsUpDown data-icon="inline-end" />
                                  </Button>
                                </PopoverTrigger>
                                <PopoverContent
                                  align="start"
                                  className="w-[var(--radix-popover-trigger-width)] p-0"
                                >
                                  <Command>
                                    <CommandInput
                                      placeholder={
                                        locale === "zh-CN"
                                          ? "搜索模型组..."
                                          : "Search groups..."
                                      }
                                    />
                                    <CommandList>
                                      <CommandEmpty>
                                        {locale === "zh-CN"
                                          ? "没有匹配的模型组"
                                          : "No matching groups"}
                                      </CommandEmpty>
                                      <CommandGroup
                                        heading={
                                          locale === "zh-CN" ? "操作" : "Action"
                                        }
                                      >
                                        <CommandItem
                                          value={`${createValue} ${createGroupName} ${item.model_name}`}
                                          forceMount
                                          onSelect={() =>
                                            selectCreateTarget(item, key)
                                          }
                                        >
                                          <div className="flex min-w-0 flex-col">
                                            <span>
                                              {locale === "zh-CN"
                                                ? "新建模型组"
                                                : "Create group"}
                                            </span>
                                            <span className="truncate text-xs text-muted-foreground">
                                              {createGroupName}
                                            </span>
                                          </div>
                                          <Check
                                            className={cn(
                                              "ml-auto",
                                              targetValue === createValue
                                                ? "opacity-100"
                                                : "opacity-0",
                                            )}
                                          />
                                        </CommandItem>
                                      </CommandGroup>
                                      {targetModelGroups.length ? (
                                        <>
                                          <CommandSeparator />
                                          <CommandGroup
                                            heading={
                                              locale === "zh-CN"
                                                ? "已有模型组"
                                                : "Existing groups"
                                            }
                                          >
                                            {targetModelGroups.map((group) => (
                                              <CommandItem
                                                key={group.id}
                                                value={group.name}
                                                onSelect={() =>
                                                  selectExistingTarget(
                                                    item,
                                                    key,
                                                    group.name,
                                                  )
                                                }
                                              >
                                                <span className="truncate">
                                                  {group.name}
                                                </span>
                                                <Check
                                                  className={cn(
                                                    "ml-auto",
                                                    item.group_name ===
                                                      group.name
                                                      ? "opacity-100"
                                                      : "opacity-0",
                                                  )}
                                                />
                                              </CommandItem>
                                            ))}
                                          </CommandGroup>
                                        </>
                                      ) : null}
                                    </CommandList>
                                  </Command>
                                </PopoverContent>
                              </Popover>
                              {targetValue === createValue ? (
                                <Input
                                  value={createGroupName}
                                  disabled={confirming}
                                  placeholder={
                                    locale === "zh-CN"
                                      ? "模型组名称"
                                      : "Group name"
                                  }
                                  aria-label={
                                    locale === "zh-CN"
                                      ? "新建模型组名称"
                                      : "New group name"
                                  }
                                  onChange={(event) => {
                                    setCreateGroupNameErrors((current) => {
                                      const next = { ...current };
                                      delete next[key];
                                      return next;
                                    });
                                    setCreateGroupNameDrafts((current) => ({
                                      ...current,
                                      [key]: event.target.value,
                                    }));
                                  }}
                                  onBlur={() => commitCreateGroupName(item)}
                                  onKeyDown={(event) =>
                                    handleCreateNameKeyDown(event, item)
                                  }
                                />
                              ) : null}
                              {targetValue === createValue ? (
                                createGroupNameErrors[key] ? (
                                  <p className="text-xs text-destructive">
                                    {createGroupNameErrors[key]}
                                  </p>
                                ) : null
                              ) : null}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex max-w-[180px] flex-wrap gap-1">
                              {item.protocols.map((protocol) => (
                                <Badge
                                  key={protocol}
                                  variant="outline"
                                  className={cn(
                                    "max-w-[120px] truncate text-xs",
                                    protocolBadgeClassName(protocol),
                                  )}
                                >
                                  {compactProtocolLabel(protocol)}
                                </Badge>
                              ))}
                              {item.skipped_reason ===
                              "protocol_extension_required" ? (
                                <Badge variant="outline" className="text-xs">
                                  {modelGroupEnsureReasonLabel(
                                    item.skipped_reason,
                                    locale,
                                  )}
                                </Badge>
                              ) : null}
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </div>

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button
                type="button"
                onClick={confirmWithDrafts}
                disabled={
                  !selectedCount || confirming || hasInvalidSelectedCreateName
                }
              >
                <RefreshCcw
                  data-icon="inline-start"
                  className={confirming ? "animate-spin" : undefined}
                />
                {locale === "zh-CN" ? "确认处理" : "Confirm"}
              </Button>
            </div>
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}

export function ModelTestDialog({
  target,
  form,
  locale,
  modelTestPrompts,
  modelTestPromptMode,
  modelTestPrompt,
  modelTestProtocol,
  modelTestResult,
  testingModel,
  onClose,
  onPromptModeChange,
  onPromptChange,
  onProtocolChange,
  onRun,
}: {
  target: ModelTestTarget | null;
  form: FormState;
  locale: Locale;
  modelTestPrompts: string[];
  modelTestPromptMode: string;
  modelTestPrompt: string;
  modelTestProtocol: ProtocolKind | null;
  modelTestResult: SiteModelTestResult | null;
  testingModel: boolean;
  onClose: () => void;
  onPromptModeChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onProtocolChange: (value: ProtocolKind) => void;
  onRun: () => void;
}) {
  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      {target !== null
        ? (() => {
            const protocolConfig =
              form.protocolConfigs[target.protocolConfigIndex];
            const model = protocolConfig?.models[target.modelIndex];
            const credentialIndex = model
              ? form.credentials.findIndex(
                  (item) => item.id === model.credential_id,
                )
              : -1;
            const credential =
              credentialIndex >= 0
                ? form.credentials[credentialIndex]
                : undefined;
            const activeBaseUrl = protocolConfig
              ? activeBaseUrlValue(form, protocolConfig).trim()
              : "";
            const supportedProtocols = modelSupportedProtocols(model);
            const selectedProtocol = selectedModelTestProtocol(
              supportedProtocols,
              modelTestProtocol,
            );
            const canTest = Boolean(
              protocolConfig &&
              model?.model_name.trim() &&
              credential?.api_key.trim() &&
              activeBaseUrl &&
              selectedProtocol &&
              modelTestPrompt.trim(),
            );
            const sourceText = [
              model?.model_name || "",
              credential
                ? credentialLabel(credential, credentialIndex, locale)
                : "",
              activeBaseUrl,
            ]
              .filter(Boolean)
              .join(" · ");
            return (
              <AppDialogContent
                className="max-w-2xl"
                title={locale === "zh-CN" ? "测试模型" : "Test model"}
              >
                <div className="grid gap-4">
                  <div className="rounded-md border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="min-w-0 flex-1 truncate text-foreground">
                        {model?.model_name || "-"}
                      </span>
                      {supportedProtocols.map((item) => (
                        <Badge
                          key={item}
                          variant="outline"
                          className={cn(
                            "max-w-[140px] truncate text-xs",
                            protocolBadgeClassName(item),
                          )}
                        >
                          {compactProtocolLabel(item)}
                        </Badge>
                      ))}
                    </div>
                    <div className="mt-1 break-all text-xs">{sourceText}</div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-[220px_minmax(0,1fr)]">
                    <div className="grid gap-3">
                      <Field>
                        <FieldLabel>
                          {locale === "zh-CN" ? "问题" : "Prompt"}
                        </FieldLabel>
                        <NativeSelect
                          className={selectClassName()}
                          value={modelTestPromptMode}
                          onChange={(event) =>
                            onPromptModeChange(event.target.value)
                          }
                        >
                          {modelTestPrompts.map((_, index) => (
                            <NativeSelectOption
                              key={index}
                              value={String(index)}
                            >
                              {locale === "zh-CN"
                                ? `预设 ${index + 1}`
                                : `Preset ${index + 1}`}
                            </NativeSelectOption>
                          ))}
                          <NativeSelectOption value="custom">
                            {locale === "zh-CN" ? "自定义" : "Custom"}
                          </NativeSelectOption>
                        </NativeSelect>
                      </Field>
                      {supportedProtocols.length > 1 ? (
                        <Field>
                          <FieldLabel>
                            {locale === "zh-CN" ? "测试协议" : "Test protocol"}
                          </FieldLabel>
                          <NativeSelect
                            className={selectClassName()}
                            value={selectedProtocol ?? ""}
                            onChange={(event) =>
                              onProtocolChange(
                                event.target.value as ProtocolKind,
                              )
                            }
                            disabled={testingModel}
                          >
                            {supportedProtocols.map((item) => (
                              <NativeSelectOption key={item} value={item}>
                                {protocolLabel(item, locale)}
                              </NativeSelectOption>
                            ))}
                          </NativeSelect>
                        </Field>
                      ) : null}
                    </div>
                    <Field>
                      <FieldLabel>
                        {locale === "zh-CN" ? "内容" : "Content"}
                      </FieldLabel>
                      <Textarea
                        className="min-h-24"
                        value={modelTestPrompt}
                        onChange={(event) => onPromptChange(event.target.value)}
                      />
                      {false ? (
                        <p className="mt-1 text-xs text-muted-foreground">
                          {locale === "zh-CN"
                            ? "Rerank 测试：首行为查询，其余行作为候选文档（每行一个）。"
                            : "Rerank test: first line is the query, remaining lines are candidate documents (one per line)."}
                        </p>
                      ) : null}
                    </Field>
                  </div>

                  {modelTestResult ? (
                    <div
                      className={cn(
                        "grid gap-2 rounded-md border px-3 py-2 text-sm",
                        modelTestResult.success
                          ? "bg-muted/20"
                          : "border-destructive/40 bg-destructive/5",
                      )}
                    >
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <Badge
                          variant="outline"
                          className={
                            modelTestResult.success
                              ? "border-primary/30 text-primary"
                              : "border-destructive/40 text-destructive"
                          }
                        >
                          {modelTestResult.success
                            ? locale === "zh-CN"
                              ? "成功"
                              : "Success"
                            : locale === "zh-CN"
                              ? "失败"
                              : "Failed"}
                        </Badge>
                        <span>HTTP {modelTestResult.status_code ?? "-"}</span>
                        <span>{modelTestResult.latency_ms}ms</span>
                      </div>
                      <div
                        className={cn(
                          "max-h-56 overflow-y-auto whitespace-pre-wrap break-words text-sm",
                          modelTestResult.success
                            ? "text-foreground"
                            : "text-destructive",
                        )}
                      >
                        {modelTestResult.success
                          ? modelTestResult.output_text ||
                            (locale === "zh-CN"
                              ? "上游返回成功，但没有可展示文本"
                              : "Upstream succeeded but returned no displayable text")
                          : modelTestResult.error_message ||
                            (locale === "zh-CN" ? "测试失败" : "Test failed")}
                      </div>
                    </div>
                  ) : null}

                  <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={onClose}
                      disabled={testingModel}
                    >
                      {locale === "zh-CN" ? "关闭" : "Close"}
                    </Button>
                    <Button
                      type="button"
                      onClick={onRun}
                      disabled={!canTest || testingModel}
                    >
                      <RefreshCcw
                        data-icon="inline-start"
                        className={testingModel ? "animate-spin" : ""}
                      />
                      {locale === "zh-CN" ? "发送测试" : "Send test"}
                    </Button>
                  </div>
                </div>
              </AppDialogContent>
            );
          })()
        : null}
    </Dialog>
  );
}

export function BatchModelTestDialog({
  open,
  locale,
  modelTestPrompts,
  batchTestPromptMode,
  batchTestPrompt,
  batchTestConcurrency,
  batchTestOptions,
  batchTestRows,
  batchTestingModels,
  onOpenChange,
  onPromptModeChange,
  onPromptChange,
  onConcurrencyChange,
  onProtocolChange,
  onRun,
}: {
  open: boolean;
  locale: Locale;
  modelTestPrompts: string[];
  batchTestPromptMode: string;
  batchTestPrompt: string;
  batchTestConcurrency: string;
  batchTestOptions: BatchModelTestOption[];
  batchTestRows: BatchModelTestRow[];
  batchTestingModels: boolean;
  onOpenChange: (open: boolean) => void;
  onPromptModeChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onConcurrencyChange: (value: string) => void;
  onProtocolChange: (key: string, protocol: ProtocolKind) => void;
  onRun: () => void;
}) {
  const multiProtocolOptions = batchTestOptions.filter(
    (item) => item.protocols.length > 1,
  );
  const testableCount = batchTestOptions.length;
  const canRun =
    testableCount > 0 && Boolean(batchTestPrompt.trim()) && !batchTestingModels;
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && batchTestingModels) return;
        onOpenChange(nextOpen);
      }}
    >
      {open ? (
        <AppDialogContent
          className="max-w-4xl"
          title={locale === "zh-CN" ? "批量测试模型" : "Batch test models"}
        >
          <div className="grid gap-4">
            <div className="rounded-md border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
              {locale === "zh-CN"
                ? `将测试 ${testableCount} 个可用模型`
                : `${testableCount} testable models`}
            </div>

            <FieldGroup>
              <div className="grid gap-3 sm:grid-cols-[220px_minmax(0,1fr)]">
                <div className="grid gap-3">
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "测试问题" : "Prompt"}
                    </FieldLabel>
                    <NativeSelect
                      className={selectClassName()}
                      value={batchTestPromptMode}
                      onChange={(event) =>
                        onPromptModeChange(event.target.value)
                      }
                      disabled={batchTestingModels}
                    >
                      {modelTestPrompts.map((_, index) => (
                        <NativeSelectOption key={index} value={String(index)}>
                          {locale === "zh-CN"
                            ? `预设 ${index + 1}`
                            : `Preset ${index + 1}`}
                        </NativeSelectOption>
                      ))}
                      <NativeSelectOption value="custom">
                        {locale === "zh-CN" ? "自定义" : "Custom"}
                      </NativeSelectOption>
                    </NativeSelect>
                  </Field>
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "并发数" : "Concurrency"}
                    </FieldLabel>
                    <Input
                      type="number"
                      min={1}
                      max={20}
                      value={batchTestConcurrency}
                      onChange={(event) =>
                        onConcurrencyChange(event.target.value)
                      }
                      disabled={batchTestingModels}
                    />
                  </Field>
                </div>
                <Field>
                  <FieldLabel>
                    {locale === "zh-CN" ? "内容" : "Content"}
                  </FieldLabel>
                  <Textarea
                    className="min-h-24"
                    value={batchTestPrompt}
                    onChange={(event) => onPromptChange(event.target.value)}
                    disabled={batchTestingModels}
                  />
                </Field>
              </div>
            </FieldGroup>

            {multiProtocolOptions.length ? (
              <FieldSet>
                <FieldLegend>
                  {locale === "zh-CN" ? "测试协议" : "Test protocol"}
                </FieldLegend>
                <div className="grid gap-3 sm:grid-cols-2">
                  {multiProtocolOptions.map((item) => (
                    <Field key={item.key}>
                      <FieldLabel className="truncate">
                        {item.modelName}
                      </FieldLabel>
                      <NativeSelect
                        className={selectClassName()}
                        value={item.selectedProtocol}
                        onChange={(event) =>
                          onProtocolChange(
                            item.key,
                            event.target.value as ProtocolKind,
                          )
                        }
                        disabled={batchTestingModels}
                      >
                        {item.protocols.map((protocol) => (
                          <NativeSelectOption key={protocol} value={protocol}>
                            {protocolLabel(protocol, locale)}
                          </NativeSelectOption>
                        ))}
                      </NativeSelect>
                    </Field>
                  ))}
                </div>
              </FieldSet>
            ) : null}

            {batchTestRows.length ? (
              <div className="overflow-hidden rounded-md border">
                <div className="border-b px-3 py-2 text-sm font-medium">
                  {locale === "zh-CN" ? "测试结果" : "Test results"}
                </div>
                <div className="max-h-80 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>
                          {locale === "zh-CN" ? "模型" : "Model"}
                        </TableHead>
                        <TableHead className="w-28">
                          {locale === "zh-CN" ? "协议" : "Protocol"}
                        </TableHead>
                        <TableHead className="w-24">
                          {locale === "zh-CN" ? "状态" : "Status"}
                        </TableHead>
                        <TableHead className="w-28">
                          {locale === "zh-CN" ? "耗时" : "Latency"}
                        </TableHead>
                        <TableHead>
                          {locale === "zh-CN" ? "结果" : "Result"}
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {batchTestRows.map((row) => {
                        const displayMessage =
                          row.message ||
                          (row.status === "running"
                            ? locale === "zh-CN"
                              ? "测试中..."
                              : "Running..."
                            : "-");
                        return (
                          <TableRow key={row.key}>
                            <TableCell className="min-w-[180px]">
                              <div className="truncate font-medium">
                                {row.modelName}
                              </div>
                              <div className="truncate text-xs text-muted-foreground">
                                {row.credentialName}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={cn(
                                  "max-w-[120px] truncate text-xs",
                                  protocolBadgeClassName(row.protocol),
                                )}
                              >
                                {compactProtocolLabel(row.protocol)}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={batchTestStatusVariant(row.status)}
                              >
                                {batchTestStatusLabel(row.status, locale)}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              <div>HTTP {row.statusCode ?? "-"}</div>
                              <div>
                                {row.latencyMs === undefined
                                  ? "-"
                                  : `${row.latencyMs}ms`}
                              </div>
                            </TableCell>
                            <TableCell>
                              <div
                                className={cn(
                                  "max-h-24 min-w-[220px] overflow-y-auto whitespace-pre-wrap break-words text-xs",
                                  row.status === "failed"
                                    ? "text-destructive"
                                    : "text-foreground",
                                )}
                              >
                                {displayMessage}
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : null}

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={batchTestingModels}
              >
                {locale === "zh-CN" ? "关闭" : "Close"}
              </Button>
              <Button type="button" onClick={onRun} disabled={!canRun}>
                <RefreshCcw
                  data-icon="inline-start"
                  className={batchTestingModels ? "animate-spin" : undefined}
                />
                {locale === "zh-CN" ? "开始测试" : "Start test"}
              </Button>
            </div>
          </div>
        </AppDialogContent>
      ) : null}
    </Dialog>
  );
}

export function ModelPickerDialog({
  open,
  availableModels,
  pickerSelectedModelKeys,
  locale,
  onOpenChange,
  onToggleModel,
  onConfirm,
  onConfirmAll,
  onCancel,
}: {
  open: boolean;
  availableModels: PickerModelItem[];
  pickerSelectedModelKeys: string[];
  locale: Locale;
  onOpenChange: (open: boolean) => void;
  onToggleModel: (key: string) => void;
  onConfirm: () => void;
  onConfirmAll: () => void;
  onCancel: () => void;
}) {
  const modelGroups = useMemo(
    () => groupPickerModels(availableModels),
    [availableModels],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <AppDialogContent
          className="max-w-3xl"
          title={locale === "zh-CN" ? "选择模型" : "Select models"}
        >
          <div className="grid gap-4">
            <div className="max-h-[58dvh] overflow-y-auto p-1 sm:max-h-[420px]">
              <div className="flex flex-wrap gap-2.5">
                {modelGroups.length ? (
                  modelGroups.map((model) => {
                    const key = genericModelKey(model);
                    const checked = pickerSelectedModelKeys.includes(key);
                    return (
                      <Button
                        key={key}
                        type="button"
                        variant="outline"
                        size="sm"
                        className={cn(
                          "max-w-full rounded-full",
                          modelBadgeClassName(checked),
                          checked ? "border-primary text-primary" : "",
                        )}
                        onClick={() => onToggleModel(key)}
                      >
                        <span className="max-w-[180px] truncate sm:max-w-[220px]">
                          {model.model_name}
                        </span>
                        <span className="text-xs">{checked ? "✓" : "+"}</span>
                      </Button>
                    );
                  })
                ) : (
                  <div className="px-3 py-6 text-sm text-muted-foreground">
                    {locale === "zh-CN"
                      ? "未获取到可选模型"
                      : "No models fetched."}
                  </div>
                )}
              </div>
            </div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button type="button" variant="outline" onClick={onCancel}>
                {locale === "zh-CN" ? "取消" : "Cancel"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={onConfirmAll}
                disabled={!modelGroups.length}
              >
                {locale === "zh-CN" ? "加入全部模型" : "Add all models"}
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
