"use client";

import { RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { AppDialogContent, Dialog } from "@/components/ui/Dialog";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { ProtocolKind } from "@/lib/api";
import { protocolLabel } from "@/lib/protocols";
import { BatchModelTestResults } from "./BatchModelTestResults";
import type {
  BatchModelTestOption,
  BatchModelTestRow,
  Locale,
} from "./channelShared";

type Props = {
  open: boolean;
  locale: Locale;
  modelTestPrompts: string[];
  batchTestPromptMode: string;
  batchTestPrompt: string;
  batchTestConcurrency: string;
  batchTestOptions: BatchModelTestOption[];
  batchTestRows: BatchModelTestRow[];
  isBatchModelTestRunning: boolean;
  onOpenChange: (open: boolean) => void;
  onPromptModeChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onConcurrencyChange: (value: string) => void;
  onProtocolChange: (key: string, protocol: ProtocolKind) => void;
  onRun: () => void;
};

/** Renders batch model test controls and result rows. */
export function BatchModelTestDialog({
  open,
  locale,
  modelTestPrompts,
  batchTestPromptMode,
  batchTestPrompt,
  batchTestConcurrency,
  batchTestOptions,
  batchTestRows,
  isBatchModelTestRunning,
  onOpenChange,
  onPromptModeChange,
  onPromptChange,
  onConcurrencyChange,
  onProtocolChange,
  onRun,
}: Props) {
  const multiProtocolOptions = batchTestOptions.filter(
    (item) => item.protocols.length > 1,
  );
  const testableCount = batchTestOptions.length;
  const canRun =
    testableCount > 0 &&
    Boolean(batchTestPrompt.trim()) &&
    !isBatchModelTestRunning;
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && isBatchModelTestRunning) return;
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
                    <Select
                      value={batchTestPromptMode}
                      onValueChange={onPromptModeChange}
                      disabled={isBatchModelTestRunning}
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
                      disabled={isBatchModelTestRunning}
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
                    disabled={isBatchModelTestRunning}
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
                      <Select
                        value={item.selectedProtocol}
                        onValueChange={(value) =>
                          onProtocolChange(item.key, value as ProtocolKind)
                        }
                        disabled={isBatchModelTestRunning}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {item.protocols.map((protocol) => (
                            <SelectItem key={protocol} value={protocol}>
                              {protocolLabel(protocol, locale)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </Field>
                  ))}
                </div>
              </FieldSet>
            ) : null}

            <BatchModelTestResults rows={batchTestRows} locale={locale} />
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isBatchModelTestRunning}
              >
                {locale === "zh-CN" ? "关闭" : "Close"}
              </Button>
              <Button type="button" onClick={onRun} disabled={!canRun}>
                <RefreshCcw
                  data-icon="inline-start"
                  className={
                    isBatchModelTestRunning ? "animate-spin" : undefined
                  }
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
