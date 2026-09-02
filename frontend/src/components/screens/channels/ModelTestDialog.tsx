import { RefreshCcw } from "lucide-react";
import {
  type ModelTestDialogTarget,
  selectedModelTestProtocol,
} from "@/components/model-test/modelTestSession";
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
import type { ProtocolKind } from "@/lib/api/protocols";
import type { SiteModelTestResult } from "@/lib/api/sites";
import { cn } from "@/lib/classNames";
import {
  compactProtocolLabel,
  protocolBadgeClassName,
  protocolLabel,
} from "@/lib/protocols";
import type { Locale } from "./channelTypes";

type Props = {
  target: ModelTestDialogTarget | null;
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

/** Renders the form and result for testing a single model. */
export function ModelTestDialog({
  target,
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
  const supportedProtocols = target?.protocols ?? [];
  const selectedProtocol = selectedModelTestProtocol(
    supportedProtocols,
    modelTestProtocol,
  );
  const canTest = Boolean(
    target?.modelName.trim() && selectedProtocol && modelTestPrompt.trim(),
  );

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
                  {target.modelName || "-"}
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
              <div className="mt-1 break-all text-xs">{target.source}</div>
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
                    disabled={testingModel}
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
                  disabled={testingModel}
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

            <div className="flex justify-end">
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
