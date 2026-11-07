import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { selectedModelTestProtocol } from "@/components/model-test/modelTestSession";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { ProtocolKind } from "@/lib/api/protocols";

import type {
  ModelTestMode,
  SiteModelTestPayload,
  SiteModelTestResult,
} from "@/lib/api/sites";
import {
  fallbackCredentialName,
  formatCredentialTitle,
} from "@/lib/credentialLabels";
import { paramOverrideDraftToRules } from "@/lib/upstreamRules";
import { paramDraftsFromJson } from "./channelAdvancedJson";
import { activeBaseUrlValue, formHeaders } from "./channelForm";
import {
  modelSupportedProtocols,
  protocolConfigModelKey,
} from "./channelModels";
import type {
  FormState,
  Locale,
  ModelTestTarget,
  TestableModelOption,
} from "./channelTypes";

/** Owns available test targets and the single-model test workflow. */
export function useChannelModelTest(form: FormState, locale: Locale) {
  const [modelTestTarget, setModelTestTarget] =
    useState<ModelTestTarget | null>(null);
  const [modelTestMode, setModelTestMode] = useState<ModelTestMode>("direct");
  const [modelTestProtocol, setModelTestProtocol] =
    useState<ProtocolKind | null>(null);
  const [modelTestResult, setModelTestResult] =
    useState<SiteModelTestResult | null>(null);
  const [testingModel, setTestingModel] = useState(false);
  const abortController = useRef<AbortController | null>(null);
  const modelTestOptionByKey = useMemo(() => {
    const options = new Map<string, TestableModelOption>();
    const credentials = new Map(
      form.credentials.map(
        (credential, index) => [credential.id, { credential, index }] as const,
      ),
    );
    for (const [configIndex, config] of form.protocolConfigs.entries()) {
      if (!activeBaseUrlValue(form, config).trim()) continue;
      for (const [modelIndex, model] of config.models.entries()) {
        const key = protocolConfigModelKey(config, model);
        if (options.has(key) || !model.model_name.trim()) continue;
        const entry = credentials.get(model.credential_id);
        if (!entry?.credential.api_key.trim()) continue;
        if (
          entry.credential.base_url_ids !== null &&
          !entry.credential.base_url_ids.includes(config.base_url_id)
        )
          continue;
        const protocols = modelSupportedProtocols(model);
        if (!protocols.length) continue;
        options.set(key, {
          key,
          target: { protocolConfigIndex: configIndex, modelIndex },
          modelName: model.model_name.trim(),
          credentialName: formatCredentialTitle(
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
  const testConfig = modelTestTarget
    ? form.protocolConfigs[modelTestTarget.protocolConfigIndex]
    : undefined;
  const testModel = modelTestTarget
    ? testConfig?.models[modelTestTarget.modelIndex]
    : undefined;
  const modelTestDialogTarget = testModel
    ? { modelName: testModel.model_name, upstreamName: form.name || "-" }
    : null;
  const modelTestDeleteKey =
    testConfig && testModel
      ? protocolConfigModelKey(testConfig, testModel)
      : null;
  const modelTestProtocols = modelSupportedProtocols(testModel);
  /** Other keys of the same URL serving the tested model name. */
  const modelTestCredentialOptions = testModel
    ? Array.from(modelTestOptionByKey.values())
        .filter(
          (option) =>
            option.target.protocolConfigIndex ===
              modelTestTarget?.protocolConfigIndex &&
            option.modelName === testModel.model_name.trim(),
        )
        .map((option) => ({ value: option.key, label: option.credentialName }))
    : [];

  useEffect(() => () => abortController.current?.abort(), []);

  function buildModelTestPayload(
    target: ModelTestTarget,
    protocol: ProtocolKind | null,
    mode: ModelTestMode,
  ): SiteModelTestPayload | null {
    const config = form.protocolConfigs[target.protocolConfigIndex];
    const model = config?.models[target.modelIndex];
    const credentialIndex = model
      ? form.credentials.findIndex((item) => item.id === model.credential_id)
      : -1;
    const credential = form.credentials[credentialIndex];
    const baseUrl = config ? activeBaseUrlValue(form, config).trim() : "";
    if (
      !config ||
      !model ||
      !credential?.api_key.trim() ||
      (credential.base_url_ids !== null &&
        !credential.base_url_ids.includes(config.base_url_id)) ||
      !baseUrl
    ) {
      return null;
    }
    const selectedProtocol = selectedModelTestProtocol(
      modelSupportedProtocols(model),
      protocol,
      mode,
    );
    if (!selectedProtocol) return null;
    return {
      protocol: selectedProtocol,
      base_url_id: config.base_url_id,
      base_url: baseUrl,
      headers: formHeaders(form),
      proxy_mode: form.proxy_mode,
      channel_proxy: form.channel_proxy.trim(),
      param_override: paramOverrideDraftToRules(
        paramDraftsFromJson(form.paramsJson) ?? [],
      ),
      credential: {
        id: credential.id,
        name: credential.name.trim() || fallbackCredentialName(credentialIndex),
        api_key: credential.api_key.trim(),
        base_url_ids: credential.base_url_ids,
      },
      model_name: model.model_name.trim(),
      test_mode: mode,
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
    setModelTestProtocol(selectedModelTestProtocol(protocols, null));
    setModelTestMode("direct");
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
    abortController.current?.abort();
    abortController.current = null;
    setTestingModel(false);
    setModelTestTarget(null);
    setModelTestProtocol(null);
    setModelTestResult(null);
  }

  function changeModelTestProtocol(protocol: ProtocolKind) {
    setModelTestProtocol(protocol);
    setModelTestResult(null);
  }

  function changeModelTestCredential(key: string) {
    const option = modelTestOptionByKey.get(key);
    if (!option) return;
    setModelTestTarget(option.target);
    setModelTestProtocol(
      selectedModelTestProtocol(
        option.protocols,
        modelTestProtocol,
        modelTestMode,
      ),
    );
    setModelTestResult(null);
  }

  function changeModelTestMode(mode: ModelTestMode) {
    setModelTestMode(mode);
    setModelTestProtocol(
      selectedModelTestProtocol(modelTestProtocols, null, mode),
    );
    setModelTestResult(null);
  }

  async function runModelTest() {
    const payload = modelTestTarget
      ? buildModelTestPayload(modelTestTarget, modelTestProtocol, modelTestMode)
      : null;
    if (!payload) {
      toast.error(
        locale === "zh-CN"
          ? "测试参数不完整"
          : "Test parameters are incomplete",
      );
      return;
    }
    const controller = new AbortController();
    abortController.current?.abort();
    abortController.current = controller;
    setTestingModel(true);
    setModelTestResult(null);
    const startedAt = performance.now();
    try {
      const result = await apiRequest<SiteModelTestResult>(
        "/admin/site-model-tests",
        {
          method: "POST",
          body: JSON.stringify(payload),
          signal: controller.signal,
        },
      );
      if (controller.signal.aborted) return;
      setModelTestResult(result);
    } catch (error) {
      if (controller.signal.aborted) return;
      setModelTestResult({
        success: false,
        status_code: null,
        latency_ms: Math.round(performance.now() - startedAt),
        model_name: payload.model_name,
        credential_id: payload.credential.id,
        output_text: "",
        error_message: getApiErrorMessage(
          error,
          locale === "zh-CN" ? "模型测试失败" : "Model test failed",
        ),
      });
    } finally {
      if (abortController.current === controller) {
        abortController.current = null;
        setTestingModel(false);
      }
    }
  }

  return {
    changeModelTestMode,
    changeModelTestProtocol,
    closeModelTest,
    changeModelTestCredential,
    modelTestCredentialOptions,
    modelTestDialogTarget,
    modelTestDeleteKey,
    modelTestMode,
    modelTestProtocol,
    modelTestProtocols,
    modelTestResult,
    openAggregateModelTest,
    runModelTest,
    testingModel,
  };
}
