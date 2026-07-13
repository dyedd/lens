"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  apiRequest,
  type ProtocolKind,
  type SiteModelTestPayload,
  type SiteModelTestResult,
} from "@/lib/api";
import {
  selectedModelTestProtocol,
  type BatchModelTestOption,
  type BatchModelTestRow,
  type Locale,
  type ModelTestTarget,
  type TestableModelOption,
} from "./channelShared";

type PayloadBuilder = (
  target: ModelTestTarget,
  protocol: ProtocolKind | null,
  prompt: string,
) => SiteModelTestPayload | null;

/** Owns batch model-test selection, concurrency, and results. */
export function useBatchModelTest({
  locale,
  prompts,
  optionByKey,
  buildPayload,
}: {
  locale: Locale;
  prompts: string[];
  optionByKey: Map<string, TestableModelOption>;
  buildPayload: PayloadBuilder;
}) {
  const [batchModelTestOpen, setBatchModelTestOpen] = useState(false);
  const [isBatchModelTestRunning, setIsBatchModelTestRunning] = useState(false);
  const [batchTestPromptMode, setBatchTestPromptMode] = useState("0");
  const [batchTestConcurrency, setBatchTestConcurrency] = useState("1");
  const [batchTestPrompt, setBatchTestPrompt] = useState("");
  const [protocolByKey, setProtocolByKey] = useState<
    Record<string, ProtocolKind>
  >({});
  const [batchTestRows, setBatchTestRows] = useState<BatchModelTestRow[]>([]);
  const batchTestOptions = useMemo<BatchModelTestOption[]>(() => {
    const options: BatchModelTestOption[] = [];
    for (const option of optionByKey.values()) {
      const selectedProtocol = selectedModelTestProtocol(
        option.protocols,
        protocolByKey[option.key] ?? null,
      );
      if (selectedProtocol) options.push({ ...option, selectedProtocol });
    }
    return options;
  }, [optionByKey, protocolByKey]);

  function clearBatchModelTestResults() {
    setBatchModelTestOpen(false);
    setBatchTestPromptMode("0");
    setBatchTestPrompt("");
    setProtocolByKey({});
    setBatchTestRows([]);
  }
  function openBatchModelTestDialog() {
    setBatchTestPromptMode("0");
    setBatchTestPrompt(prompts[0] || "");
    setProtocolByKey({});
    setBatchTestRows([]);
    setBatchModelTestOpen(true);
  }
  function changeBatchTestPromptMode(value: string) {
    setBatchTestPromptMode(value);
    setBatchTestRows([]);
    if (value !== "custom") setBatchTestPrompt(prompts[Number(value)] || "");
  }
  function changeBatchTestPrompt(value: string) {
    if (batchTestPromptMode !== "custom") setBatchTestPromptMode("custom");
    setBatchTestPrompt(value);
    setBatchTestRows([]);
  }
  function changeBatchTestProtocol(key: string, protocol: ProtocolKind) {
    setProtocolByKey((current) => ({ ...current, [key]: protocol }));
    setBatchTestRows([]);
  }
  function updateRow(key: string, patch: Partial<BatchModelTestRow>) {
    setBatchTestRows((current) =>
      current.map((row) => (row.key === key ? { ...row, ...patch } : row)),
    );
  }
  async function runBatchModelTests() {
    const prompt = batchTestPrompt.trim();
    if (!prompt) {
      toast.error(locale === "zh-CN" ? "测试问题为空" : "Test prompt is empty");
      return;
    }
    const entries: Array<{
      key: string;
      payload: SiteModelTestPayload;
      row: BatchModelTestRow;
    }> = [];
    for (const option of batchTestOptions) {
      const payload = buildPayload(
        option.target,
        option.selectedProtocol,
        prompt,
      );
      if (!payload) continue;
      const key = `${option.key}:${payload.protocol}`;
      entries.push({
        key,
        payload,
        row: {
          key,
          modelName: payload.model_name,
          credentialName: payload.credential.name,
          protocol: payload.protocol,
          status: "pending",
          statusCode: null,
          latencyMs: undefined,
          message: "",
        },
      });
    }
    if (!entries.length) {
      toast.error(
        locale === "zh-CN" ? "没有可测试的模型" : "No testable models",
      );
      return;
    }
    setBatchTestPrompt(prompt);
    setBatchTestRows(entries.map((entry) => entry.row));
    const parsed = Number.parseInt(batchTestConcurrency, 10);
    const concurrency = Math.max(
      1,
      Math.min(Number.isFinite(parsed) ? parsed : 1, 20, entries.length),
    );
    let cursor = 0;
    let succeeded = 0;
    let failed = 0;
    setIsBatchModelTestRunning(true);
    try {
      await Promise.all(
        Array.from({ length: concurrency }, async () => {
          while (cursor < entries.length) {
            const entry = entries[cursor++];
            updateRow(entry.key, { status: "running", message: "" });
            try {
              const result = await apiRequest<SiteModelTestResult>(
                "/admin/site-model-tests",
                { method: "POST", body: JSON.stringify(entry.payload) },
              );
              updateRow(entry.key, {
                status: result.success ? "success" : "failed",
                statusCode: result.status_code ?? null,
                latencyMs: result.latency_ms,
                message: result.success
                  ? result.output_text ||
                    (locale === "zh-CN"
                      ? "上游返回成功，但没有可展示文本"
                      : "Upstream succeeded but returned no displayable text")
                  : result.error_message ||
                    (locale === "zh-CN" ? "测试失败" : "Model test failed"),
              });
              if (result.success) succeeded += 1;
              else failed += 1;
            } catch (error) {
              updateRow(entry.key, {
                status: "failed",
                statusCode: null,
                latencyMs: undefined,
                message:
                  error instanceof Error
                    ? error.message
                    : locale === "zh-CN"
                      ? "测试请求失败"
                      : "Test request failed",
              });
              failed += 1;
            }
          }
        }),
      );
      const message =
        locale === "zh-CN"
          ? `批量测试完成：成功 ${succeeded}，失败 ${failed}`
          : `Batch test finished: ${succeeded} succeeded, ${failed} failed`;
      toast[failed ? "error" : "success"](message);
    } finally {
      setIsBatchModelTestRunning(false);
    }
  }
  return {
    batchModelTestOpen,
    setBatchModelTestOpen,
    isBatchModelTestRunning,
    batchTestPromptMode,
    batchTestConcurrency,
    setBatchTestConcurrency,
    batchTestPrompt,
    batchTestOptions,
    batchTestRows,
    clearBatchModelTestResults,
    openBatchModelTestDialog,
    changeBatchTestPromptMode,
    changeBatchTestPrompt,
    changeBatchTestProtocol,
    runBatchModelTests,
  };
}
