"use client";

import { RefreshCcw } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import { Field, FieldLabel } from "@/components/ui/Field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { cn } from "@/lib/utils";
import type { ProtocolKind, SiteModelTestResult } from "@/lib/api";
import {
  compactProtocolLabel,
  protocolBadgeClassName,
  protocolLabel,
} from "@/lib/protocols";
import {
  activeBaseUrlValue,
  credentialLabel,
  modelSupportedProtocols,
  selectedModelTestProtocol,
} from "./channelShared";
import type { FormState, Locale, ModelTestTarget } from "./channelShared";

type Props = {
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
};

/** Renders the form and result for testing a single channel model. */
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
}: Props) {
  const protocolConfig =
    target === null
      ? undefined
      : form.protocolConfigs[target.protocolConfigIndex];
  const model =
    target === null ? undefined : protocolConfig?.models[target.modelIndex];
  const credentialIndex = model
    ? form.credentials.findIndex((item) => item.id === model.credential_id)
    : -1;
  const credential =
    credentialIndex >= 0 ? form.credentials[credentialIndex] : undefined;
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
    credential ? credentialLabel(credential, credentialIndex, locale) : "",
    activeBaseUrl,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      {target !== null ? (
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
                  <Select
                    value={modelTestPromptMode}
                    onValueChange={onPromptModeChange}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {modelTestPrompts.map((_, index) => (
                        <SelectItem key={index} value={String(index)}>
                          {locale === "zh-CN"
                            ? `预设 ${index + 1}`
                            : `Preset ${index + 1}`}
                        </SelectItem>
                      ))}
                      <SelectItem value="custom">
                        {locale === "zh-CN" ? "自定义" : "Custom"}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                {supportedProtocols.length > 1 ? (
                  <Field>
                    <FieldLabel>
                      {locale === "zh-CN" ? "测试协议" : "Test protocol"}
                    </FieldLabel>
                    <Select
                      value={selectedProtocol ?? ""}
                      onValueChange={(value) =>
                        onProtocolChange(value as ProtocolKind)
                      }
                      disabled={testingModel}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {supportedProtocols.map((item) => (
                          <SelectItem key={item} value={item}>
                            {protocolLabel(item, locale)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
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
      ) : null}
    </Dialog>
  );
}
