// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { ChannelModelsDialog } from "./ChannelModelsDialog";
import { ChannelRemoteModelsDialog } from "./ChannelRemoteModelsDialog";
import { emptyForm } from "./channelForm";
import type { FormState, PickerModelItem } from "./channelTypes";
import { useChannelModelPicker } from "./useChannelModelPicker";

const API_URLS = [
  { id: "url-primary", url: "https://primary.example/v1", kind: "default" },
  { id: "url-secondary", url: "https://secondary.example/v1", kind: "default" },
] as const;

function createChannelForm(existingEnabled = true): FormState {
  const form = emptyForm();
  form.name = "Primary";
  form.base_urls = API_URLS.map((item) => ({ ...item }));
  form.credentials = [
    {
      id: "credential-primary",
      name: "Primary key",
      api_key: "test-key",
      rate_source: "none",
      rate_protocol_config_id: "",
      rate_group: "",
      rate_multiplier: null,
      rate_observed_at: null,
      rate_last_synced_at: null,
      rate_last_error: "",
      base_url_ids: null,
    },
  ];
  form.protocolConfigs = API_URLS.map((item, index) => ({
    id: `protocol-${index + 1}`,
    base_url_id: item.id,
    credential_ids: ["credential-primary"],
    protocols: ["openai_chat"],
    models:
      index === 1 && !existingEnabled
        ? [
            {
              credential_id: "credential-primary",
              model_name: "model-from-primary",
              enabled: false,
              protocols: ["openai_chat"],
              modelIdsByProtocol: {},
              context_window: null,
              upstream_context_window: null,
            },
          ]
        : [],
  }));
  return form;
}

function createModelResult() {
  return [
    {
      credential_id: "credential-primary",
      credential_name: "Primary key",
      model_name: "model-from-primary",
      protocol: "openai_chat",
      context_window: 32_768,
    },
  ];
}

function PickerWorkflow({
  onImport,
  initialForm,
}: {
  onImport: (items: PickerModelItem[]) => void;
  initialForm: FormState;
}) {
  const [form, setForm] = useState(initialForm);
  const [remoteOpen, setRemoteOpen] = useState(false);
  const picker = useChannelModelPicker({
    form,
    setForm,
    sessionKey: "create-channel",
    locale: "en-US",
  });

  return (
    <>
      <output data-testid="channel-models">
        {form.protocolConfigs
          .flatMap((config) => config.models.map((model) => model.model_name))
          .join(",")}
      </output>
      <output data-testid="model-enablements">
        {form.protocolConfigs
          .flatMap((config) => config.models)
          .map((model) => `${model.model_name}:${model.enabled}`)
          .join(",")}
      </output>
      <ChannelModelsDialog
        open
        locale="en-US"
        channelName={form.name}
        supportsModelListing={form.supports_model_listing}
        models={[]}
        saving={false}
        fetching={picker.fetching}
        onOpenChange={() => {}}
        onSave={() => {}}
        onToggleEnabled={() => {}}
        onUpdateProtocols={() => {}}
        onUpdateContextWindow={() => {}}
        onDelete={() => {}}
        onTest={() => {}}
        testing={false}
        detecting={picker.detecting}
        onDetectProtocols={picker.detectModelProtocols}
        onOpenRemote={() => setRemoteOpen(true)}
        credentialOptions={[{ id: "credential-primary", label: "Primary key" }]}
        onApplyModelPattern={picker.applyModelPattern}
      >
        <ChannelRemoteModelsDialog
          open={remoteOpen}
          locale="en-US"
          channelName={form.name}
          loading={picker.fetching}
          importing={picker.detecting}
          onOpenChange={setRemoteOpen}
          onLoad={picker.discoverRemoteCatalog}
          onImport={(items) => {
            picker.importRemoteModels(items);
            onImport(items);
          }}
        />
      </ChannelModelsDialog>
    </>
  );
}

let root: Root | undefined;
let container: HTMLDivElement | undefined;
let queryClient: QueryClient;

function findButton(label: string) {
  return Array.from(document.querySelectorAll("button")).find(
    (button) =>
      (button.getAttribute("aria-label") ?? button.textContent?.trim()) ===
      label,
  );
}

async function clickButton(label: string) {
  const button = findButton(label);
  expect(button, `Expected a button containing "${label}"`).toBeDefined();
  await act(async () => button?.click());
}

async function waitFor(condition: () => boolean) {
  await act(async () => {
    const deadline = Date.now() + 3_000;
    while (!condition() && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
  });
  expect(condition()).toBe(true);
}

async function renderWorkflow(
  onImport = vi.fn(),
  initialForm = createChannelForm(),
) {
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  await act(async () => {
    root?.render(
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <PickerWorkflow initialForm={initialForm} onImport={onImport} />
        </TooltipProvider>
      </QueryClientProvider>,
    );
  });
  return onImport;
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal(
    "ResizeObserver",
    class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  vi.stubGlobal("PointerEvent", MouseEvent);
  Element.prototype.scrollIntoView = vi.fn();
  window.scrollTo = vi.fn();
});

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount());
  }
  root = undefined;
  container?.remove();
  container = undefined;
  queryClient.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("channel model discovery workflow", () => {
  it("imports results from a successful URL when another URL fails", async () => {
    const requestedUrls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        const payload = JSON.parse(String(init?.body)) as {
          base_url_id: string;
        };
        requestedUrls.push(payload.base_url_id);
        if (payload.base_url_id === "url-secondary") {
          return new Response(
            JSON.stringify({ error: { message: "Secondary URL failed" } }),
            {
              status: 503,
              headers: { "content-type": "application/json" },
            },
          );
        }
        return new Response(JSON.stringify(createModelResult()), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );
    const onImport = await renderWorkflow();

    await clickButton("Fetch model list");
    await waitFor(() => Boolean(findButton("model-from-primary")));
    expect(requestedUrls).toEqual(["url-primary", "url-secondary"]);
    await clickButton("model-from-primary");
    await clickButton("Add selected 1");
    await waitFor(() => screenText("channel-models") === "model-from-primary");
    expect(onImport).toHaveBeenCalledWith([
      expect.objectContaining({
        model_name: "model-from-primary",
        protocol_config_id: "protocol-1",
      }),
    ]);
  });

  it("ignores discovery results that arrive after cancel", async () => {
    const pendingResponses: Array<{
      baseUrlId: string;
      resolve: (response: Response) => void;
      signal: AbortSignal;
    }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        const payload = JSON.parse(String(init?.body)) as {
          base_url_id: string;
        };
        return new Promise<Response>((resolve) => {
          pendingResponses.push({
            baseUrlId: payload.base_url_id,
            resolve,
            signal: init?.signal as AbortSignal,
          });
        });
      }),
    );
    const onImport = await renderWorkflow();

    await clickButton("Fetch model list");
    await waitFor(() => pendingResponses.length === 2);
    await clickButton("Cancel");

    expect(pendingResponses.every((request) => request.signal.aborted)).toBe(
      true,
    );
    await act(async () => {
      for (const request of pendingResponses) {
        request.resolve(
          new Response(JSON.stringify(createModelResult()), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        );
      }
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(screenText("channel-models")).toBe("");
    expect(onImport).not.toHaveBeenCalled();
  });

  it("preserves a disabled model state when importing it into another URL", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(createModelResult()), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        ),
      ),
    );
    await renderWorkflow(vi.fn(), createChannelForm(false));

    await clickButton("Fetch model list");
    await waitFor(() => Boolean(findButton("model-from-primary")));
    await clickButton("model-from-primary");
    await clickButton("Add selected 1");
    await waitFor(() => (screenText("channel-models") ?? "").includes(","));

    expect(screenText("model-enablements")).toBe(
      "model-from-primary:false,model-from-primary:false",
    );
  });

  it("drops selections removed by a refreshed upstream catalog", async () => {
    let requestCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL) => {
        requestCount += 1;
        const items = requestCount === 1 ? createModelResult() : [];
        return Response.json(items);
      }),
    );
    const onImport = await renderWorkflow();

    await clickButton("Fetch model list");
    await waitFor(() => Boolean(findButton("model-from-primary")));
    await clickButton("model-from-primary");
    await clickButton("Reload");
    await waitFor(() => Boolean(findButton("Add selected 0")));

    expect(findButton("Add selected 0")?.disabled).toBe(true);
    expect(onImport).not.toHaveBeenCalled();
  });

  it("keeps the model rule open when no catalog entries match", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json([])),
    );
    const onImport = await renderWorkflow();

    await clickButton("Model rule");
    const input = document.querySelector<HTMLTextAreaElement>(
      "#channel-model-pattern",
    );
    expect(input).not.toBeNull();
    await act(async () => {
      if (!input) return;
      const setValue = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value",
      )?.set;
      setValue?.call(input, "^missing-model$");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await clickButton("Apply to list");

    expect(document.querySelector("#channel-model-pattern")).not.toBeNull();
    expect(onImport).not.toHaveBeenCalled();
  });
});

function screenText(testId: string) {
  return document.querySelector(`[data-testid="${testId}"]`)?.textContent;
}
