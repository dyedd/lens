"use client";

import { useMemo } from "react";
import { RefreshCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AppDialogContent, Dialog } from "@/components/ui/dialog";
import {
  Field,
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { ProtocolKind, SiteModelTestResult } from "@/lib/api";
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
