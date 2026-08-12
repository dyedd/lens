"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  apiRequest,
  getApiErrorMessage,
  type ProtocolKind,
  type SiteModelTestResult,
} from "@/lib/api";
import { selectedModelTestProtocol } from "./modelTestSession";

export type BatchModelTestStatus = "pending" | "running" | "success" | "failed";

export type BatchModelTestRow = {
  key: string;
  modelName: string;
  credentialName: string;
  protocol: ProtocolKind;
  status: BatchModelTestStatus;
  statusCode: number | null;
  latencyMs?: number;
  message: string;
};

export type BatchModelTestSource<TTarget> = {
  key: string;
  target: TTarget;
  modelName: string;
  credentialName: string;
  protocols: ProtocolKind[];
};

export type BatchModelTestOption = {
  key: string;
  modelName: string;
  credentialName: string;
  protocols: ProtocolKind[];
  selectedProtocol: ProtocolKind;
};

type PreparedBatchModelTestRequest = {
  path: string;
  payload: object;
  modelName: string;
  credentialName: string;
  protocol: ProtocolKind;
};

type Options<TTarget> = {
  locale: "zh-CN" | "en-US";
  prompts: string[];
  optionByKey: ReadonlyMap<string, BatchModelTestSource<TTarget>>;
  prepareRequest: (
    target: TTarget,
    protocol: ProtocolKind,
    prompt: string,
  ) => PreparedBatchModelTestRequest | null;
};

/** Owns batch model-test prompts, concurrency, cancellation, and result rows. */
export function useBatchModelTestSession<TTarget>({
  locale,
  prompts,
  optionByKey,
  prepareRequest,
}: Options<TTarget>) {
  const [batchModelTestOpen, setBatchModelTestOpen] = useState(false);
  const [isBatchModelTestRunning, setIsBatchModelTestRunning] = useState(false);
  const [batchTestPromptMode, setBatchTestPromptMode] = useState("0");
  const [batchTestConcurrency, setBatchTestConcurrency] = useState("1");
  const [batchTestPrompt, setBatchTestPrompt] = useState("");
  const [protocolByKey, setProtocolByKey] = useState<
    Record<string, ProtocolKind>
  >({});
  const [batchTestRows, setBatchTestRows] = useState<BatchModelTestRow[]>([]);
  const abortController = useRef<AbortController | null>(null);
  const batchTestOptions = useMemo<BatchModelTestOption[]>(() => {
    const options: BatchModelTestOption[] = [];
    for (const option of optionByKey.values()) {
      const selectedProtocol = selectedModelTestProtocol(
        option.protocols,
        protocolByKey[option.key] ?? null,
      );
      if (!selectedProtocol) continue;
      options.push({
        key: option.key,
        modelName: option.modelName,
        credentialName: option.credentialName,
        protocols: option.protocols,
        selectedProtocol,
      });
    }
    return options;
  }, [optionByKey, protocolByKey]);

  useEffect(() => () => abortController.current?.abort(), []);

  function cancelBatchModelTests() {
    abortController.current?.abort();
    abortController.current = null;
    setIsBatchModelTestRunning(false);
  }

  function clearBatchModelTestResults() {
    cancelBatchModelTests();
    setBatchModelTestOpen(false);
    setBatchTestPromptMode("0");
    setBatchTestPrompt("");
    setProtocolByKey({});
    setBatchTestRows([]);
  }

  function changeBatchModelTestOpen(open: boolean) {
    if (!open) cancelBatchModelTests();
    setBatchModelTestOpen(open);
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
      request: PreparedBatchModelTestRequest;
      row: BatchModelTestRow;
    }> = [];
    for (const option of batchTestOptions) {
      const source = optionByKey.get(option.key);
      if (!source) continue;
      const request = prepareRequest(
        source.target,
        option.selectedProtocol,
        prompt,
      );
      if (!request) continue;
      const key = `${option.key}:${request.protocol}`;
      entries.push({
        key,
        request,
        row: {
          key,
          modelName: request.modelName,
          credentialName: request.credentialName,
          protocol: request.protocol,
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
    const parsedConcurrency = Number.parseInt(batchTestConcurrency, 10);
    const concurrency = Math.max(
      1,
      Math.min(
        Number.isFinite(parsedConcurrency) ? parsedConcurrency : 1,
        20,
        entries.length,
      ),
    );
    let cursor = 0;
    let succeeded = 0;
    let failed = 0;
    const controller = new AbortController();
    abortController.current?.abort();
    abortController.current = controller;
    setIsBatchModelTestRunning(true);
    try {
      await Promise.all(
        Array.from({ length: concurrency }, async () => {
          while (!controller.signal.aborted && cursor < entries.length) {
            const entry = entries[cursor++];
            updateRow(entry.key, { status: "running", message: "" });
            try {
              const result = await apiRequest<SiteModelTestResult>(
                entry.request.path,
                {
                  method: "POST",
                  body: JSON.stringify(entry.request.payload),
                  signal: controller.signal,
                },
              );
              updateRow(entry.key, {
                status: result.success ? "success" : "failed",
                statusCode: result.status_code,
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
              if (controller.signal.aborted) return;
              updateRow(entry.key, {
                status: "failed",
                statusCode: null,
                latencyMs: undefined,
                message: getApiErrorMessage(
                  error,
                  locale === "zh-CN" ? "测试请求失败" : "Test request failed",
                ),
              });
              failed += 1;
            }
          }
        }),
      );
      if (controller.signal.aborted) return;
      toast[failed ? "error" : "success"](
        locale === "zh-CN"
          ? `批量测试完成：成功 ${succeeded}，失败 ${failed}`
          : `Batch test finished: ${succeeded} succeeded, ${failed} failed`,
      );
    } finally {
      if (abortController.current === controller) {
        abortController.current = null;
        setIsBatchModelTestRunning(false);
      }
    }
  }

  return {
    batchModelTestOpen,
    batchTestConcurrency,
    batchTestOptions,
    batchTestPrompt,
    batchTestPromptMode,
    batchTestRows,
    changeBatchModelTestOpen,
    changeBatchTestPrompt,
    changeBatchTestPromptMode,
    changeBatchTestProtocol,
    clearBatchModelTestResults,
    isBatchModelTestRunning,
    openBatchModelTestDialog,
    runBatchModelTests,
    setBatchTestConcurrency,
  };
}
