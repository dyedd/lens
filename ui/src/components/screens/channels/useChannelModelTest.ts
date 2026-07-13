"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  apiRequest,
  getApiErrorMessage,
  type ProtocolKind,
  type SettingItem,
  type SiteModelTestPayload,
  type SiteModelTestResult,
} from "@/lib/api";
import {
  MODEL_TEST_PROMPTS_SETTING_KEY,
  parseModelTestPrompts,
} from "@/lib/modelTestPrompts";
import {
  activeBaseUrlValue,
  credentialLabel,
  fallbackCredentialName,
  formHeaders,
  modelSupportedProtocols,
  protocolConfigModelKey,
  selectedModelTestProtocol,
  type FormState,
  type Locale,
  type ModelTestTarget,
  type TestableModelOption,
} from "./channelShared";

/** Owns available test targets and the single-model test workflow. */
export function useChannelModelTest(form: FormState, locale: Locale) {
  const [modelTestTarget, setModelTestTarget] =
    useState<ModelTestTarget | null>(null);
  const [modelTestPromptMode, setModelTestPromptMode] = useState("0");
  const [modelTestPrompt, setModelTestPrompt] = useState("");
  const [modelTestProtocol, setModelTestProtocol] =
    useState<ProtocolKind | null>(null);
  const [modelTestResult, setModelTestResult] =
    useState<SiteModelTestResult | null>(null);
  const [testingModel, setTestingModel] = useState(false);
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<SettingItem[]>("/admin/settings"),
    staleTime: 5 * 60_000,
  });
  const modelTestPrompts = useMemo(() => {
    const mapping = new Map(
      (settings ?? []).map((item) => [item.key, item.value]),
    );
    return parseModelTestPrompts(mapping.get(MODEL_TEST_PROMPTS_SETTING_KEY));
  }, [settings]);
  const modelTestOptionByKey = useMemo(() => {
    const options = new Map<string, TestableModelOption>();
    const credentials = new Map(
      form.credentials.map(
        (credential, index) => [credential.id, { credential, index }] as const,
      ),
    );
    for (const [configIndex, config] of form.protocolConfigs.entries()) {
      if (!config.enabled || !activeBaseUrlValue(form, config).trim()) continue;
      for (const [modelIndex, model] of config.models.entries()) {
        const key = protocolConfigModelKey(configIndex, config, model);
        if (options.has(key) || !model.model_name.trim()) continue;
        const entry = credentials.get(model.credential_id);
        if (!entry?.credential.api_key.trim()) continue;
        const protocols = modelSupportedProtocols(model);
        if (!protocols.length) continue;
        options.set(key, {
          key,
          target: { protocolConfigIndex: configIndex, modelIndex },
          modelName: model.model_name.trim(),
          credentialName: credentialLabel(
            entry.credential,
            entry.index,
            locale,
          ),
          protocols,
        });
      }
    }
    return options;
  }, [form, locale]);

  function buildModelTestPayload(
    target: ModelTestTarget,
    protocol: ProtocolKind | null,
    promptValue: string,
  ): SiteModelTestPayload | null {
    const config = form.protocolConfigs[target.protocolConfigIndex];
    const model = config?.models[target.modelIndex];
    const credentialIndex = model
      ? form.credentials.findIndex((item) => item.id === model.credential_id)
      : -1;
    const credential = form.credentials[credentialIndex];
    const baseUrl = config ? activeBaseUrlValue(form, config).trim() : "";
    const prompt = promptValue.trim();
    if (
      !config ||
      !model ||
      !credential ||
      !credential.api_key.trim() ||
      !baseUrl ||
      !prompt
    ) {
      return null;
    }
    const selectedProtocol = selectedModelTestProtocol(
      modelSupportedProtocols(model),
      protocol,
    );
    if (!selectedProtocol) return null;
    return {
      protocol: selectedProtocol,
      base_url: baseUrl,
      headers: formHeaders(config),
      proxy_mode: config.proxy_mode,
      channel_proxy: config.channel_proxy.trim(),
      param_override: config.param_override.trim(),
      credential: {
        id: credential.id,
        name: credential.name.trim() || fallbackCredentialName(credentialIndex),
        api_key: credential.api_key.trim(),
      },
      model_name: model.model_name.trim(),
      prompt,
    };
  }
  function openModelTest(configIndex: number, modelIndex: number) {
    const protocols = modelSupportedProtocols(
      form.protocolConfigs[configIndex]?.models[modelIndex],
    );
    if (!protocols.length) {
      toast.error(
        locale === "zh-CN"
          ? "请先为模型选择有效协议"
          : "Select a valid protocol for the model first",
      );
      return;
    }
    setModelTestTarget({ protocolConfigIndex: configIndex, modelIndex });
    setModelTestProtocol(protocols[0]);
    setModelTestPromptMode("0");
    setModelTestPrompt(modelTestPrompts[0] || "");
    setModelTestResult(null);
  }
  function openAggregateModelTest(key: string) {
    const option = modelTestOptionByKey.get(key);
    if (!option) {
      toast.error(
        locale === "zh-CN"
          ? "测试参数不完整"
          : "Test parameters are incomplete",
      );
      return;
    }
    openModelTest(option.target.protocolConfigIndex, option.target.modelIndex);
  }
  function closeModelTest() {
    if (testingModel) return;
    setModelTestTarget(null);
    setModelTestProtocol(null);
    setModelTestResult(null);
  }
  function changeModelTestPromptMode(value: string) {
    setModelTestPromptMode(value);
    if (value !== "custom" && modelTestPrompts[Number(value)]) {
      setModelTestPrompt(modelTestPrompts[Number(value)]);
    }
  }
  function changeModelTestPrompt(value: string) {
    setModelTestPrompt(value);
    if (modelTestPromptMode !== "custom") setModelTestPromptMode("custom");
  }
  async function runModelTest() {
    if (!modelTestTarget) return;
    const payload = buildModelTestPayload(
      modelTestTarget,
      modelTestProtocol,
      modelTestPrompt,
    );
    if (!payload) {
      toast.error(
        locale === "zh-CN"
          ? "测试参数不完整"
          : "Test parameters are incomplete",
      );
      return;
    }
    setTestingModel(true);
    setModelTestResult(null);
    try {
      const result = await apiRequest<SiteModelTestResult>(
        "/admin/site-model-tests",
        { method: "POST", body: JSON.stringify(payload) },
      );
      setModelTestResult(result);
      toast[result.success ? "success" : "error"](
        result.success
          ? locale === "zh-CN"
            ? "模型测试成功"
            : "Model test succeeded"
          : locale === "zh-CN"
            ? "模型测试失败"
            : "Model test failed",
      );
    } catch (error) {
      const message = getApiErrorMessage(
        error,
        locale === "zh-CN" ? "模型测试失败" : "Model test failed",
      );
      setModelTestResult({
        success: false,
        status_code: null,
        latency_ms: 0,
        model_name: payload.model_name,
        credential_id: payload.credential.id,
        output_text: "",
        error_message: message,
      });
    } finally {
      setTestingModel(false);
    }
  }
  return {
    modelTestTarget,
    modelTestPromptMode,
    modelTestPrompt,
    modelTestProtocol,
    setModelTestProtocol,
    modelTestResult,
    testingModel,
    modelTestPrompts,
    modelTestOptionByKey,
    buildModelTestPayload,
    openAggregateModelTest,
    closeModelTest,
    changeModelTestPromptMode,
    changeModelTestPrompt,
    runModelTest,
  };
}
