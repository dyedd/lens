import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { ProtocolKind } from "@/lib/api/protocols";
import type { SiteModelTestResult } from "@/lib/api/sites";
import { selectedModelTestProtocol } from "./modelTestSession";

export type BatchModelTestRow = {
  key: string;
  modelName: string;
  credentialName: string;
  protocol: ProtocolKind | null;
  protocols: ProtocolKind[];
  result: SiteModelTestResult | null;
};

export type BatchModelTestSource<TTarget> = {
  key: string;
  target: TTarget;
  modelName: string;
  credentialName: string;
  protocols: ProtocolKind[];
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
  optionByKey?: ReadonlyMap<string, BatchModelTestSource<TTarget>>;
  prepareRequest: (
    target: TTarget,
    protocol: ProtocolKind,
    prompt: string,
  ) => PreparedBatchModelTestRequest | null;
};

/** Runs each model probe and keeps the results for the shared detail dialog. */
export function useBatchModelTestSession<TTarget>({
  locale,
  prompts,
  optionByKey,
  prepareRequest,
}: Options<TTarget>) {
  const [batchModelTestOpen, setBatchModelTestOpen] = useState(false);
  const [isBatchModelTestRunning, setIsBatchModelTestRunning] = useState(false);
  const [sources, setSources] = useState<BatchModelTestSource<TTarget>[]>([]);
  const [batchTestPromptMode, setBatchTestPromptMode] = useState("0");
  const [batchTestPrompt, setBatchTestPrompt] = useState("");
  const [batchTestRows, setBatchTestRows] = useState<BatchModelTestRow[]>([]);
  const abortController = useRef<AbortController | null>(null);

  useEffect(() => () => abortController.current?.abort(), []);

  function cancelBatchModelTests() {
    abortController.current?.abort();
    abortController.current = null;
    setIsBatchModelTestRunning(false);
  }

  function clearBatchModelTestResults() {
    cancelBatchModelTests();
    setBatchModelTestOpen(false);
    setBatchTestRows([]);
  }

  function changeBatchModelTestOpen(open: boolean) {
    if (!open) cancelBatchModelTests();
    setBatchModelTestOpen(open);
  }

  function openBatchModelTestDialog(
    nextSources: Iterable<
      BatchModelTestSource<TTarget>
    > = optionByKey?.values() ?? [],
  ) {
    const available = Array.from(nextSources).filter(
      (source) => source.protocols.length > 0,
    );
    if (!available.length) {
      toast.error(
        locale === "zh-CN" ? "没有可测试的模型" : "No testable models",
      );
      return;
    }
    setSources(available);
    setBatchTestPromptMode(prompts.length ? "0" : "custom");
    setBatchTestPrompt(prompts[0] || "");
    setBatchTestRows(
      available.map((source) => ({
        key: source.key,
        modelName: source.modelName,
        credentialName: source.credentialName,
        protocols: source.protocols,
        protocol: selectedModelTestProtocol(source.protocols, null),
        result: null,
      })),
    );
    setBatchModelTestOpen(true);
  }

  function changeBatchTestPromptMode(value: string) {
    setBatchTestPromptMode(value);
    if (value !== "custom") setBatchTestPrompt(prompts[Number(value)] || "");
    setBatchTestRows((rows) => rows.map((row) => ({ ...row, result: null })));
  }

  function changeBatchTestPrompt(value: string) {
    setBatchTestPrompt(value);
    setBatchTestPromptMode("custom");
    setBatchTestRows((rows) => rows.map((row) => ({ ...row, result: null })));
  }

  function changeBatchTestProtocol(key: string, protocol: ProtocolKind) {
    setBatchTestRows((rows) =>
      rows.map((row) =>
        row.key === key ? { ...row, protocol, result: null } : row,
      ),
    );
  }

  async function runBatchModelTests() {
    const prompt = batchTestPrompt.trim();
    if (!prompt || batchTestRows.some((row) => !row.protocol)) return;
    const entries: Array<{
      key: string;
      request: PreparedBatchModelTestRequest;
    }> = [];
    const selectedProtocols = new Map(
      batchTestRows.map((row) => [row.key, row.protocol]),
    );
    for (const source of sources) {
      const protocol = selectedModelTestProtocol(
        source.protocols,
        selectedProtocols.get(source.key) ?? null,
      );
      if (!protocol) continue;
      const request = prepareRequest(source.target, protocol, prompt);
      if (request) entries.push({ key: source.key, request });
    }
    if (!entries.length) {
      toast.error(
        locale === "zh-CN" ? "没有可测试的模型" : "No testable models",
      );
      return;
    }

    const controller = new AbortController();
    abortController.current?.abort();
    abortController.current = controller;
    setBatchTestRows((rows) => rows.map((row) => ({ ...row, result: null })));
    setIsBatchModelTestRunning(true);
    try {
      for (const { key, request } of entries) {
        if (controller.signal.aborted) return;
        let result: SiteModelTestResult;
        try {
          result = await apiRequest<SiteModelTestResult>(request.path, {
            method: "POST",
            body: JSON.stringify(request.payload),
            signal: controller.signal,
          });
        } catch (error) {
          if (controller.signal.aborted) return;
          result = {
            success: false,
            status_code: null,
            latency_ms: 0,
            model_name: request.modelName,
            credential_id: "",
            output_text: "",
            error_message: getApiErrorMessage(
              error,
              locale === "zh-CN" ? "测试请求失败" : "Test request failed",
            ),
          };
        }
        if (controller.signal.aborted) return;
        setBatchTestRows((current) =>
          current.map((row) => (row.key === key ? { ...row, result } : row)),
        );
      }
    } finally {
      if (abortController.current === controller) {
        abortController.current = null;
        setIsBatchModelTestRunning(false);
      }
    }
  }

  return {
    batchModelTestOpen,
    batchTestPrompt,
    batchTestPromptMode,
    prompts,
    batchTestRows,
    changeBatchTestPrompt,
    changeBatchTestPromptMode,
    changeBatchTestProtocol,
    changeBatchModelTestOpen,
    clearBatchModelTestResults,
    isBatchModelTestRunning,
    openBatchModelTestDialog,
    runBatchModelTests,
  };
}
